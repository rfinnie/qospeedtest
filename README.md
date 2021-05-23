# qospeedtest - Quick-and-Dirty OoklaServer Speed Test

qospeedtest is a CLI to test against [OoklaServer](https://support.ookla.com/hc/en-us/articles/234578528-OoklaServer-Installation-Linux-Unix), the backends used by [speedtest.net](https://speedtest.net/) for speed tests (though not to be confused with the legacy backend server format previously used by speedtest.net).  OoklaServer servers will typically have a base URL in the format "http://example.com:8080/", with https also being in use, as well as port 5060.

qospeedtest emulates the communication order done by speedtest.net, but uses a different calculation algorithm.  qospeedtest begins with a small arbitrary size (100 KiB for download, 10 KiB for upload), calculates the speed, and uses this to prepare for the next round, targeting (by default) 1 second downloads/uploads per request.  The speed is fed into an [EWMA](https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average) with a weight of 8, and the process continues until the EWMA is greater than the last request.

(The "quick" in the name refers to the quick-and-dirty reverse engineering and reimplementation of OoklaServer.  The actual tests tend to be slower, but will still typically finish within a minute or so.)

## Installation

Python 3 is required, with the `requests` and `yaml` libraries.  The package may be installed (`python3 setup.py install`), or run directly from the git checkout.

## Usage

```
$ qospeedtest http://example.com:8080/
Testing download speed from http://example.com:8080/
Download speed: 109.07 Mbps, 383.08 MiB received in 37 requests
Testing upload speed to http://example.com:8080/
Upload speed: 11.27 Mbps, 57.99 MiB sent in 49 requests
```

Several more options are available; see `qospeedtest --help` for more information.

For a list of public servers, see [speedtest.net's server XML list](https://www.speedtest.net/speedtest-servers-static.php), particularly the "host" property of each entry.  (Ignore "url" and "url2" which are legacy endpoints, which qospeedtest does not support.)

## Server

Also included is qospeedtest-server, a WSGI server which is a mostly feature-complete clone of OoklaServer.  It works as a server for qospeedtest, and theoretically could serve as the base for an official speedtest.net server.

The recommended usage is via Gunicorn:

```
$ gunicorn3 -b 0.0.0.0:8080 -w 4 -k gthread qospeedtest.wsgi:application
```

`-k gthread` is needed for Keep-alive and 100 Continue support, both needed for accurate client measurement.

`qospeedtest-server` may be run directly, and if Gunicorn is installed, it will use that with a default minimal configuration.  Otherwise it will use wsgiref, which is suitable only for basic testing and definitely not production use, as it doesn't have Keep-alive or 100 Continue support (or even HTTP 1.1 support).
