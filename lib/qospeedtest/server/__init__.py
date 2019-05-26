import os
import urllib.parse


class RandomGenerator(object):
    def __init__(self, byte_count):
        self.byte_count = byte_count
        self.left = self.byte_count

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self.left <= 0:
            self.left = self.byte_count
            raise StopIteration()
        to_return = self.left if self.left < 1024 else 1024
        self.left -= to_return
        return os.urandom(to_return)


class ServerApplication():
    def __call__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        self.query_params = {}
        if 'QUERY_STRING' in self.environ:
            self.query_params = urllib.parse.parse_qs(self.environ['QUERY_STRING'])
        if hasattr(self, 'method_{}'.format(self.environ['REQUEST_METHOD'])):
            return getattr(self, 'method_{}'.format(self.environ['REQUEST_METHOD']))()
        else:
            body = 'Method Not Allowed\n'.encode('UTF-8')
            self.start_response('405 Method Not Allowed', [
                ('Content-Type', 'text/plain'),
                ('Content-Length', str(len(body))),
                ])
            return [body]

    def process_hello(self):
        body = 'hello\n'.encode('UTF-8')
        self.start_response('200 OK', [
            ('Content-Type', 'text/plain; charset=UTF-8'),
            ('Content-Length', str(len(body))),
            ])
        return [body]

    def process_download(self):
        output_len = 0
        if 'size' in self.query_params:
            try:
                output_len = int(self.query_params['size'][0])
            except Exception:
                pass
        if output_len <= 0:
            output_len = 10737418240
        self.start_response('200 OK', [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Length', str(output_len)),
            ])
        return RandomGenerator(output_len)

    def process_upload(self):
        content_length = int(self.environ['CONTENT_LENGTH'])
        left = content_length
        while left > 0:
            to_read = left if left < 1024 else 1024
            left -= to_read
            self.environ['wsgi.input'].read(to_read)
        body = 'size={}\n'.format(content_length).encode('UTF-8')
        self.start_response('200 OK', [
            ('Content-Type', 'text/plain; charset=UTF-8'),
            ('Content-Length', str(len(body))),
            ])
        return [body]

    def method_POST(self):
        if self.environ['PATH_INFO'] == '/upload':
            return self.process_upload()
        else:
            body = 'Not Found\n'.encode('UTF-8')
            self.start_response('404 Not Found', [
                ('Content-Type', 'text/plain; charset=UTF-8'),
                ('Content-Length', str(len(body))),
                ])
            return [body]

    def method_OPTIONS(self):
        headers = [
            ('Content-Type', 'text/plain; charset=UTF-8'),
            ('Content-Length', str(0)),
            ('Access-Control-Allow-Methods', 'OPTIONS, GET, POST'),
        ]
        if 'HTTP_ORIGIN' in self.environ:
            headers.append(('Access-Control-Allow-Origin', self.environ['HTTP_ORIGIN']))
            headers.append(('Vary', 'Origin'))
        if 'HTTP_ACCESS_CONTROL_REQUEST_HEADERS' in self.environ:
            headers.append(('Access-Control-Allow-Headers', self.environ['HTTP_ACCESS_CONTROL_REQUEST_HEADERS']))
        self.start_response('200 OK', headers)
        return []

    def method_GET(self):
        if self.environ['PATH_INFO'] == '/hello':
            return self.process_hello()
        elif self.environ['PATH_INFO'] == '/download':
            return self.process_download()
        else:
            body = 'Not Found\n'.encode('UTF-8')
            self.start_response('404 Not Found', [
                ('Content-Type', 'text/plain; charset=UTF-8'),
                ('Content-Length', str(len(body))),
                ])
            return [body]


def standalone_gunicorn():
    from gunicorn.app.base import BaseApplication

    class StandaloneApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super(StandaloneApplication, self).__init__()

        def load_config(self):
            config = dict([(key, value) for key, value in self.options.items()
                           if key in self.cfg.settings and value is not None])
            for key, value in config.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    options = {
        'bind': '0.0.0.0:8080',
        'worker_class': 'gthread',
    }
    application = ServerApplication()
    server = StandaloneApplication(application, options)
    server.run()


def standalone_wsgiref():
    # wsgiref.simple_server is unsuitable for production, as it supports
    # neither HTTP 1.1 nor 100 Continue.
    from wsgiref.simple_server import make_server

    application = ServerApplication()
    server = make_server('0.0.0.0', 8080, application)
    server.serve_forever()


def main():
    try:
        standalone_gunicorn()
    except ImportError:
        standalone_wsgiref()


if __name__ == '__main__':
    main()
