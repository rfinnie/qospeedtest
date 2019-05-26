#!/usr/bin/env python3

import argparse
import datetime
import logging
import os
import sys
import uuid

import requests
import yaml


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

    def add_datapoint(self, number):
        if self._ewma_state == 0:
            self._ewma_state = number * self._weight
        else:
            self._ewma_state += (number - (self._ewma_state / self._weight))

    def get_average(self):
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
            '--skip-download', action='store_true',
            help='Skip download test',
        )
        parser.add_argument(
            '--skip-upload', action='store_true',
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

        with requests.Session() as session:
            session_guid = guid()
            timed_request(session.get, url_base + 'hello', params={'nocache': guid(), 'guid': session_guid})
            projected_bytes = self.args.initial_download if mode == 'download' else self.args.initial_upload
            ewma = EWMA(self.args.ewma_weight)
            total_transferred = 0
            raw_count = 1
            transfer_count = 0

            while True:
                if mode == 'download':
                    logging.debug('Requesting payload of {}B from {}download'.format(pretty_number(projected_bytes, divisor=1024), url_base))
                else:
                    logging.debug('Sending payload of {}B to {}upload'.format(pretty_number(projected_bytes, divisor=1024), url_base))
                request_guid = guid()
                if mode == 'download':
                    t_elapsed, r = timed_request(
                        session.get,
                        url_base + 'download',
                        params={'size': projected_bytes, 'nocache': request_guid, 'guid': session_guid}
                    )
                    t_elapsed -= r.elapsed
                    raw_count += 1
                    transfer_bytes = len(r.content)
                else:
                    random_payload = os.urandom(projected_bytes)
                    t_elapsed, _ = timed_request(
                        session.post,
                        url_base + 'upload',
                        params={'nocache': request_guid, 'guid': session_guid},
                        data=random_payload,
                    )
                    raw_count += 2
                    transfer_bytes = projected_bytes

                transfer_count += 1
                total_transferred += transfer_bytes
                bytes_per_second = transfer_bytes / t_elapsed.total_seconds()
                ewma.add_datapoint(bytes_per_second)
                ewma_average = ewma.get_average()
                if bytes_per_second < ewma_average:
                    break
                projected_bytes = int(ewma_average * self.args.target_seconds)

            bps = ewma.get_average() * 8.0
            if mode == 'download':
                logging.info('Download speed: {}bps, {}B received in {} downloads ({} raw requests)'.format(
                    pretty_number(bps), pretty_number(total_transferred, divisor=1024), transfer_count, raw_count
                ))
            else:
                logging.info('Upload speed: {}bps, {}B sent in {} uploads ({} raw requests)'.format(
                    pretty_number(bps), pretty_number(total_transferred, divisor=1024), transfer_count, raw_count
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

        if not self.args.skip_download:
            self.do_test('download', url_base)
        if not self.args.skip_upload:
            self.do_test('upload', url_base)


def main():
    return QOSpeedTest().main()
