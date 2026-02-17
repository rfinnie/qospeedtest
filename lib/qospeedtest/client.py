# SPDX-PackageName: qospeedtest
# SPDX-PackageSupplier: Ryan Finnie <ryan@finnie.org>
# SPDX-PackageDownloadLocation: https://github.com/rfinnie/qospeedtest
# SPDX-FileCopyrightText: © 2019 Ryan Finnie <ryan@finnie.org>
# SPDX-License-Identifier: MPL-2.0

import argparse
import datetime
import logging
import math
import os
import pathlib
import statistics
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests
import yaml

from . import __version__
from . import EWMA, SemiRandomGenerator
from . import guid, si_number


class QOSpeedTest:
    args = None
    user_config = None
    http_session = None
    session_guid = None
    is_tty = sys.stdin.isatty()

    def __init__(self):
        self.user_config = {}

    def parse_args(self, argv=None):
        """Parse user arguments."""
        if argv is None:
            argv = sys.argv

        program = os.path.basename(sys.argv[0])
        parser = argparse.ArgumentParser(
            description="{} ({})".format(program, __version__),
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog=program,
        )

        parser.add_argument(
            "--version",
            "-V",
            action="version",
            version=__version__,
            help="report the program version",
        )

        action_group = parser.add_mutually_exclusive_group(required=False)
        action_group.add_argument("server", type=str, nargs="?", help="Speed test server profile or URL")
        action_group.add_argument("--list", action="store_true", help="List saved servers.")
        action_group.add_argument("--nearby", action="store_true", help="List nearby speedtest.net servers")

        parser.add_argument("--debug", action="store_true", help="Print extra debugging information.")
        parser.add_argument(
            "--ewma-weight",
            type=float,
            default=8.0,
            help="EWMA weight for speed confidence",
        )
        parser.add_argument(
            "--target-seconds",
            type=lambda x: datetime.timedelta(seconds=float(x)),
            default=datetime.timedelta(seconds=1.0),
            dest="target",
            help="Length of each request to try for",
        )
        parser.add_argument("--no-download", action="store_true", help="Skip download test")
        parser.add_argument("--no-upload", action="store_true", help="Skip upload test")
        parser.add_argument(
            "--initial-download",
            type=int,
            default=(1024 * 1024),
            help="Number of bytes to request for the initial download",
        )
        parser.add_argument(
            "--initial-upload",
            type=int,
            default=(1024 * 128),
            help="Number of bytes to send for the initial upload",
        )
        parser.add_argument(
            "--minimum-samples",
            type=int,
            default=10,
            help="Minimum number of samples to gather per individual download/upload test",
        )
        parser.add_argument(
            "--maximum-samples",
            type=int,
            default=50,
            help="Maximum number of samples to gather per individual download/upload test",
        )

        args = parser.parse_args(args=argv[1:])
        return args

    def load_user_config(self):
        base_config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
        yaml_file = pathlib.Path(os.path.join(base_config_dir, "qospeedtest", "config.yaml"))
        if yaml_file.exists():
            with yaml_file.open() as f:
                self.user_config = yaml.safe_load(f)

        if "servers" not in self.user_config:
            self.user_config["servers"] = {}

        if ("default_server" not in self.user_config) or (self.user_config["default_server"] not in self.user_config["servers"]):
            self.user_config["default_server"] = None

    def get_speedtest_net_servers(self):
        base_cache_dir = os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
        xml_cache_file = pathlib.Path(
            os.path.join(
                base_cache_dir,
                "qospeedtest",
                "speedtest-servers-static.xml",
            )
        )
        if xml_cache_file.exists() and (xml_cache_file.stat().st_mtime >= (time.time() - (60 * 60 * 24))):
            logging.debug("Using cached speedtest-servers-static.xml")
            root = ET.fromstring(xml_cache_file.read_text())
            return root.iter("server")

        res = self.http_session.get("https://www.speedtest.net/speedtest-servers-static.php")
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError:
            if xml_cache_file.exists():
                logging.exception("Warning: Received error from speedtest.net servers list, using outdated cache instead")
                root = ET.fromstring(xml_cache_file.read_text())
                return root.iter("server")
            else:
                raise
        else:
            root = ET.fromstring(res.text)
            xml_cache_file.parent.mkdir(parents=True, exist_ok=True)
            xml_cache_file.write_text(res.text)
            return root.iter("server")

    def print_nearby_remote(self):
        for i, server in enumerate(self.get_speedtest_net_servers()):
            logging.info(
                "http://{}/\t{}, {}\t{}".format(
                    server.attrib["host"],
                    server.attrib["name"],
                    server.attrib["cc"],
                    server.attrib["sponsor"],
                )
            )
            if i >= 9:
                return

    def st_request(self, *args, **kwargs):
        kwargs["params"] = kwargs.get("params", {}).copy()
        kwargs["params"]["guid"] = self.session_guid
        kwargs["params"]["nocache"] = guid()
        r = self.http_session.request(*args, **kwargs)
        r.raise_for_status()
        return r

    def do_test(self, mode, url_base):
        if mode == "download":
            logging.info("Testing download speed from {}".format(url_base))
        else:
            logging.info("Testing upload speed to {}".format(url_base))

        r = self.st_request("GET", url_base + "hello")
        hello_response = r.text.strip()
        logging.debug("Server: {}".format(hello_response))
        if not hello_response.startswith("hello"):
            raise ValueError("Expected hello response from server, got: {}".format(hello_response))

        projected_bytes = self.args.initial_download if mode == "download" else self.args.initial_upload
        ewma_bps = EWMA(self.args.ewma_weight)
        ewma_time = EWMA(self.args.ewma_weight, state=datetime.timedelta())
        transfer_count = 0
        transfer_bytes_sum = 0
        bps_sample_list = []
        rampup_mode = True
        test_start = datetime.datetime.now()

        while True:
            if mode == "download":
                logging.debug(
                    "Requesting payload of {payload:0.02f} {payload.prefix}B from {url}download".format(
                        payload=si_number(projected_bytes, binary=True), url=url_base
                    )
                )
                with self.st_request(
                    "GET",
                    url_base + "download",
                    params={"size": projected_bytes},
                    stream=True,
                ) as r:
                    t_start = datetime.datetime.now()
                    transfer_bytes = 0
                    for i in r.iter_content(chunk_size=None):
                        transfer_bytes += len(i)
                    t_end = datetime.datetime.now()
                    t_transfer = t_end - t_start
                if projected_bytes != transfer_bytes:
                    raise ValueError("Requested {} bytes from server, got {}".format(projected_bytes, transfer_bytes))
            else:
                logging.debug(
                    "Sending payload of {payload:0.02f} {payload.prefix}B to {url}upload".format(
                        payload=si_number(projected_bytes, binary=True), url=url_base
                    )
                )
                random_payload = b"".join(SemiRandomGenerator(projected_bytes))
                # requests supports data= being a generator, but then uses
                # Chunked transfer encoding, which the servers do not support,
                # so we must sent the data to requests in one go.
                r = self.st_request("POST", url_base + "upload", data=random_payload, stream=True)
                t_transfer = r.elapsed
                response_size = int(urllib.parse.parse_qs(r.text.strip())["size"][0])
                if response_size != projected_bytes:
                    raise ValueError("Expected confirmation of {} bytes from server, got {}".format(projected_bytes, response_size))
                transfer_bytes = projected_bytes

            bps = transfer_bytes / t_transfer.total_seconds() * 8.0
            transfer_bytes_sum += transfer_bytes
            transfer_count += 1
            logging.debug(
                "Request processing time: {elapsed}, payload: "
                "{payload:0.02f} {payload.prefix}B in {transfer} "
                "({bps:0.02f} {bps.prefix}b/s)".format(
                    elapsed=r.elapsed,
                    payload=si_number(transfer_bytes, binary=True),
                    transfer=t_transfer,
                    bps=si_number(bps),
                )
            )

            if self.is_tty and not self.args.debug:

                def confidence_bar(fraction, length=20):
                    fraction = 1 - abs((fraction / 1.0) - 1)
                    fraction = 1 - (math.log(((1 - fraction) * 25) + 1) / math.log(25 + 1))
                    progress = int(fraction * length)
                    return ("!" * progress) + ("." * (length - progress))

                sys.stderr.write(
                    "\r\x1b[K{dots} {spinner} {bps:0.02f} {bps.prefix}b/s ({count})".format(
                        dots=("?" * 20 if rampup_mode else confidence_bar(ewma_time.average / self.args.target)),
                        spinner=["/", "-", "\\", "|"][(transfer_count - 1) % 4],
                        bps=si_number(bps if rampup_mode else ewma_bps.average),
                        count=transfer_count,
                    )
                )

            # Do not consider the first results
            if rampup_mode:
                thresh_low = self.args.target * 0.9
                thresh_high = self.args.target * 1.5
                if not (thresh_high > t_transfer > thresh_low):
                    logging.debug(
                        "Confidence not yet high on early sample "
                        "({} not within {} and {} targeting {}), "
                        "not counting toward EWMA".format(t_transfer, thresh_low, thresh_high, self.args.target)
                    )
                    projected_bytes = int(bps * self.args.target.total_seconds() / 8.0)
                    continue
                else:
                    rampup_mode = False

            ewma_bps.add(bps)
            ewma_time.add(t_transfer)
            bps_sample_list.append(bps)
            logging.debug(
                "EWMA bps: {bps:0.02f} {bps.prefix}b/s, time: {time}".format(
                    bps=si_number(ewma_bps.average), time=ewma_time.average
                )
            )

            if len(bps_sample_list) >= self.args.maximum_samples:
                logging.debug("Reached maximum samples")
                break
            elif len(bps_sample_list) >= self.args.minimum_samples:
                if (self.args.target * 1.25) > ewma_time.average > (self.args.target * 0.95):
                    break

            projected_bytes = int(ewma_bps.average * self.args.target.total_seconds() / 8.0)

        test_end = datetime.datetime.now()

        if self.is_tty and not self.args.debug:
            sys.stderr.write("\r\x1b[K")
        if mode == "download":
            wording = ("Download", "received")
        else:
            wording = ("Upload", "sent")
        logging.info(
            "{type} speed: {bps:0.02f} {bps.prefix}b/s, {transfer:0.02f} {transfer.prefix}B {verb} in "
            "{time}".format(
                type=wording[0],
                bps=si_number(ewma_bps.average),
                transfer=si_number(transfer_bytes_sum, binary=True),
                verb=wording[1],
                time=(test_end - test_start),
            )
        )
        if len(bps_sample_list) > 1:
            stdev = statistics.stdev(bps_sample_list)
            logging.info(
                "Standard deviation: {stdev:0.02f} {stdev.prefix}b/s ({stdev_ratio:.1%}), "
                "lowest {min:0.02f} {min.prefix}b/s, highest {max:0.02f} {max.prefix}b/s".format(
                    stdev=si_number(stdev),
                    stdev_ratio=(stdev / ewma_bps.average),
                    min=si_number(min(bps_sample_list)),
                    max=si_number(max(bps_sample_list)),
                )
            )
        logging.info("")

    def main(self):
        self.args = self.parse_args()

        if self.args.debug:
            logging_level = logging.DEBUG
            logging_format = "%(asctime)s: %(name)s/%(levelname)s: %(message)s"
        else:
            logging_level = logging.INFO
            logging_format = "%(message)s"
        logging.basicConfig(format=logging_format, level=logging_level)

        self.load_user_config()
        self.http_session = requests.Session()
        self.http_session.headers["User-Agent"] = "qospeedtest (https://github.com/rfinnie/qospeedtest)"
        self.session_guid = guid()

        if self.args.list:
            for server in self.user_config["servers"]:
                logging.info("{}\t{}".format(server, self.user_config["servers"][server]["url"]))
            return
        elif self.args.nearby:
            return self.print_nearby_remote()
        elif self.args.server:
            if self.args.server in self.user_config["servers"]:
                url_base = self.user_config["servers"][self.args.server]["url"]
            else:
                url_base = self.args.server
        elif self.user_config["default_server"]:
            url_base = self.user_config["servers"][self.user_config["default_server"]]["url"]
            logging.info("Using default server '{}' from user configuration".format(self.user_config["default_server"]))
            logging.info("")
        else:
            speedtest_net_servers = self.get_speedtest_net_servers()
            server = next(speedtest_net_servers)
            url_base = "http://{}/".format(server.attrib["host"])
            logging.info(
                "Using closest speedtest.net server: {} in {}, {}".format(
                    server.attrib["sponsor"], server.attrib["name"], server.attrib["cc"]
                )
            )
            logging.info("")

        if not url_base.endswith("/"):
            url_base += "/"

        if not self.args.no_download:
            self.do_test("download", url_base)
        if not self.args.no_upload:
            self.do_test("upload", url_base)


def main():
    try:
        return QOSpeedTest().main()
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
