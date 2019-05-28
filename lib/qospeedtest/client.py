#!/usr/bin/env python3

import argparse
import datetime
import logging
import os
import statistics
import sys
import uuid

import requests
import yaml

from . import SemiRandomGenerator

__version__ = '0.0.0'


def guid():
    return str(uuid.uuid4())


def pretty_number(n, divisor=1000, rollover=1.0, limit=0, format='{number:0.02f} {prefix}'):
    prefixes = [
        ('k', 'Ki'), ('M', 'Mi'), ('G', 'Gi'), ('T', 'Ti'),
        ('P', 'Pi'), ('E', 'Ei'), ('Z', 'Zi'), ('Y', 'Yi'),
    ]
    if limit == 0:
        limit = len(prefixes)

    count = 0
    p = ''
    for prefix in prefixes:
        if n < (divisor * rollover):
            break
        if count >= limit:
            break
        count += 1
        n = n / float(divisor)
        p = prefix[1] if divisor == 1024 else prefix[0]
    return format.format(number=n, prefix=p)


class EWMA:
    _weight = 8.0
    _ewma_state = 0

    def __init__(self, weight=8.0):
        self._weight = weight

    def add(self, number):
        if self._ewma_state == 0:
            self._ewma_state = number * self._weight
        else:
            self._ewma_state += (number - (self._ewma_state / self._weight))

    @property
    def average(self):
        return self._ewma_state / self._weight


def timed_request(method, *args, **kwargs):
    t_begin = datetime.datetime.now()
    r = method(*args, **kwargs)
    t_end = datetime.datetime.now()
    r.raise_for_status()
    return t_end - t_begin, r


class QOSpeedTest:
    args = None
    user_config = None

    def __init__(self):
        self.user_config = {}

    def parse_args(self, argv=None):
        """Parse user arguments."""
        if argv is None:
            argv = sys.argv

        parser = argparse.ArgumentParser(
            description='vanityhash ({})'.format(__version__),
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog=os.path.basename(argv[0]),
        )

        parser.add_argument(
            '--version', '-V', action='version',
            version=__version__,
            help='report the program version',
        )

        parser.add_argument(
            'server', type=str,
            help='Speed test server profile or URL',
        )

        parser.add_argument(
            '--debug', action='store_true',
            help='Print extra debugging information.',
        )
        parser.add_argument(
            '--ewma-weight', type=float, default=8.0,
            help='EWMA weight for speed confidence',
        )
        parser.add_argument(
            '--target-seconds', type=float, default=1.0,
            help='Length of each request to try for',
        )
        parser.add_argument(
            '--no-download', action='store_true',
            help='Skip download test',
        )
        parser.add_argument(
            '--no-upload', action='store_true',
            help='Skip upload test',
        )
        parser.add_argument(
            '--initial-download', type=int, default=102400,
            help='Number of bytes to request for the initial download',
        )
        parser.add_argument(
            '--initial-upload', type=int, default=10240,
            help='Number of bytes to send for the initial upload',
        )
        parser.add_argument(
            '--initial-samples', type=int, default=3,
            help='Number of ramp-up samples to not count against final calculations',
        )
        parser.add_argument(
            '--minimum-samples', type=int, default=10,
            help='Minimum number of samples to gather per individual download/upload test',
        )
        parser.add_argument(
            '--maximum-samples', type=int, default=50,
            help='Maximum number of samples to gather per individual download/upload test',
        )

        args = parser.parse_args(args=argv[1:])
        return args

    def load_user_config(self):
        yaml_file = os.path.join(os.path.expanduser('~'), '.config', 'qospeedtest', 'config.yaml')
        if os.path.exists(yaml_file):
            with open(yaml_file) as f:
                self.user_config = yaml.safe_load(f)

        if 'servers' not in self.user_config:
            self.user_config['servers'] = {}

    def do_test(self, mode, url_base):
        if mode == 'download':
            logging.info('Testing download speed from {}'.format(url_base))
        else:
            logging.info('Testing upload speed to {}'.format(url_base))

        target_td = datetime.timedelta(seconds=self.args.target_seconds)
        with requests.Session() as session:
            session_guid = guid()
            timed_request(session.get, url_base + 'hello', params={'nocache': guid(), 'guid': session_guid})
            projected_bytes = self.args.initial_download if mode == 'download' else self.args.initial_upload
            ewma_bps = EWMA(self.args.ewma_weight)
            ewma_time = EWMA(self.args.ewma_weight)
            transfer_count = 0
            transfer_bytes_sum = 0
            bps_sample_list = []

            while True:
                if mode == 'download':
                    logging.debug('Requesting payload of {}B from {}download'.format(
                        pretty_number(projected_bytes, divisor=1024), url_base),
                    )
                else:
                    logging.debug('Sending payload of {}B to {}upload'.format(
                        pretty_number(projected_bytes, divisor=1024), url_base),
                    )
                request_guid = guid()
                if mode == 'download':
                    t_request, r = timed_request(
                        session.get,
                        url_base + 'download',
                        params={'size': projected_bytes, 'nocache': request_guid, 'guid': session_guid},
                        stream=True,
                    )
                    t_start = datetime.datetime.now()
                    transfer_bytes = 0
                    for i in r.iter_content(None):
                        transfer_bytes += len(i)
                    t_end = datetime.datetime.now()
                    t_transfer = t_end - t_start
                else:
                    random_payload = b''.join(SemiRandomGenerator(projected_bytes))
                    t_request, r = timed_request(
                        session.post,
                        url_base + 'upload',
                        params={'nocache': request_guid, 'guid': session_guid},
                        data=random_payload,
                    )
                    t_transfer = r.elapsed
                    transfer_bytes = projected_bytes

                bps = transfer_bytes / t_transfer.total_seconds() * 8.0
                transfer_bytes_sum += transfer_bytes
                transfer_count += 1
                logging.debug('Total request send: {}, requests elapsed: {}, payload: {}B in {} ({}b/s)'.format(
                    t_request, r.elapsed, pretty_number(transfer_bytes, divisor=1024), t_transfer,
                    pretty_number(bps),
                ))

                # Do not consider the first results
                if(transfer_count <= self.args.initial_samples):
                    projected_bytes = int(bps * self.args.target_seconds * 1.05 / 8.0)
                    continue

                ewma_bps.add(bps)
                ewma_time.add(t_transfer)
                bps_sample_list.append(bps)
                logging.debug('EWMA bps: {}b/s, time: {}'.format(
                    pretty_number(ewma_bps.average), ewma_time.average,
                ))

                if len(bps_sample_list) >= self.args.maximum_samples:
                    logging.debug('Reached maximum samples')
                    break
                elif len(bps_sample_list) >= self.args.minimum_samples:
                    if ewma_time.average >= (target_td * 0.95):
                        break

                projected_bytes = int(ewma_bps.average * self.args.target_seconds * 1.05 / 8.0)

            if mode == 'download':
                wording = ('Download', 'received')
            else:
                wording = ('Upload', 'sent')
            logging.info('{} speed: {}b/s, {}B {} in {} requests'.format(
                wording[0], pretty_number(ewma_bps.average), pretty_number(transfer_bytes_sum, divisor=1024),
                wording[1], transfer_count,
            ))
            stdev = statistics.stdev(bps_sample_list)
            logging.info('Standard deviation: {}b/s ({:.1%}), lowest/highest single request: {}b/s, {}b/s'.format(
                pretty_number(stdev), stdev / ewma_bps.average,
                pretty_number(min(bps_sample_list)), pretty_number(max(bps_sample_list)),
            ))

    def main(self):
        self.args = self.parse_args()

        if self.args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(
            format='%(asctime)s: %(name)s/%(levelname)s: %(message)s',
            level=logging_level
        )

        self.load_user_config()

        if self.args.server in self.user_config['servers']:
            url_base = self.user_config['servers'][self.args.server]['url']
        else:
            url_base = self.args.server

        if not url_base.endswith('/'):
            url_base += '/'

        if not self.args.no_download:
            self.do_test('download', url_base)
        if not self.args.no_upload:
            self.do_test('upload', url_base)


def main():
    return QOSpeedTest().main()


if __name__ == '__main__':
    sys.exit(main())
