# SPDX-PackageSummary: Quick-and-Dirty OoklaServer-compatible Speed Test
# SPDX-FileCopyrightText: Copyright (C) 2019-2021 Ryan Finnie <ryan@finnie.org>
# SPDX-License-Identifier: MPL-2.0

import logging
import urllib.parse

from . import __version__
from . import SemiRandomGenerator


class ServerApplication:
    def __call__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        self.path = self.environ["PATH_INFO"].lstrip("/")
        self.query_params = {}
        if "QUERY_STRING" in self.environ:
            self.query_params = urllib.parse.parse_qs(self.environ["QUERY_STRING"])
        if hasattr(self, "method_{}".format(self.environ["REQUEST_METHOD"])):
            return getattr(self, "method_{}".format(self.environ["REQUEST_METHOD"]))()
        else:
            return self.simple_response("Method Not Allowed", "405 Method Not Allowed")

    def simple_response(self, message, code_str="200 OK"):
        body = "{}\n".format(message).encode("UTF-8")
        self.start_response(
            code_str,
            [
                ("Content-Type", "text/plain; charset=UTF-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    def process_hello(self):
        return self.simple_response("hello qospeedtest-server {}".format(__version__))

    def process_download(self):
        output_len = 0
        if "size" in self.query_params:
            try:
                output_len = int(self.query_params["size"][0])
            except Exception:
                pass
        if output_len <= 0:
            output_len = 10737418240
        self.start_response(
            "200 OK",
            [
                ("Content-Type", "application/octet-stream"),
                ("Content-Length", str(output_len)),
            ],
        )
        return SemiRandomGenerator(output_len)

    def process_upload(self):
        content_length = int(self.environ["CONTENT_LENGTH"])
        left = content_length
        while left > 0:
            to_read = left if left < 1048576 else 1048576
            left -= to_read
            self.environ["wsgi.input"].read(to_read)
        return self.simple_response("size={}".format(content_length))

    def method_POST(self):
        try:
            int(self.environ["CONTENT_LENGTH"])
        except (KeyError, ValueError):
            return self.simple_response("Bad Request", "400 Bad Request")
        if self.path == "upload":
            return self.process_upload()
        else:
            return self.simple_response("Not Found", "404 Not Found")

    def method_OPTIONS(self):
        headers = [
            ("Content-Type", "text/plain; charset=UTF-8"),
            ("Content-Length", str(0)),
            ("Access-Control-Allow-Methods", "OPTIONS, GET, POST"),
        ]
        if "HTTP_ORIGIN" in self.environ:
            headers.append(("Access-Control-Allow-Origin", self.environ["HTTP_ORIGIN"]))
            headers.append(("Vary", "Origin"))
        if "HTTP_ACCESS_CONTROL_REQUEST_HEADERS" in self.environ:
            headers.append(
                (
                    "Access-Control-Allow-Headers",
                    self.environ["HTTP_ACCESS_CONTROL_REQUEST_HEADERS"],
                )
            )
        self.start_response("200 OK", headers)
        return []

    def method_GET(self):
        if self.path == "hello":
            return self.process_hello()
        elif self.path == "download":
            return self.process_download()
        else:
            return self.simple_response("Not Found", "404 Not Found")


def standalone_gunicorn():
    from gunicorn.app.base import BaseApplication

    class StandaloneApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super(StandaloneApplication, self).__init__()

        def load_config(self):
            config = dict([(key, value) for key, value in self.options.items() if key in self.cfg.settings and value is not None])
            for key, value in config.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    options = {"bind": "0.0.0.0:8080", "worker_class": "gthread"}
    application = ServerApplication()
    server = StandaloneApplication(application, options)
    server.run()


def standalone_wsgiref():
    logging.warning("wsgiref.simple_server is unsuitable for production, as it supports neither HTTP 1.1 nor 100 Continue.")
    from wsgiref.simple_server import make_server

    application = ServerApplication()
    server = make_server("0.0.0.0", 8080, application)
    server.serve_forever()


def main():
    logging.basicConfig(format="%(asctime)s: %(name)s/%(levelname)s: %(message)s", level=logging.INFO)
    try:
        standalone_gunicorn()
    except ImportError:
        standalone_wsgiref()


if __name__ == "__main__":
    main()
