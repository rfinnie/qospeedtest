# qospeedtest - Quick OoklaServer Speed Test

qospeedtest is a CLI to test against [OoklaServer](https://support.ookla.com/hc/en-us/articles/234578528-OoklaServer-Installation-Linux-Unix), the backends used by [speedtest.net](https://speedtest.net/) for speed tests (though not to be confused with the legacy backend server format previously used by speedtest.net).  OoklaServer servers will typically have a base URL in the format "http://example.com:8080/", with https also being in use, as well as port 5060.

qospeedtest emulates the communication order done by speedtest.net, but uses a different calculation algorithm.  qospeedtest begins with a small arbitrary size (100 KiB for download, 10 KiB for upload), calculates the speed, and uses this to prepare for the next round, targeting (by default) 1 second downloads/uploads per request.  The speed is fed into an [EWMA](https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average) with a weight of 8, and the process continues until the EWMA is greater than the last request.

(The "quick" in the name refers to the quick-and-dirty reverse engineering and reimplementation of OoklaServer.  The actual tests tend to be slower, but will still typically finish within a minute or so.)

## Usage

```
$ qospeedtest http://example.com:8080/
2019-05-25 14:24:59,742: root/INFO: Testing download speed from http://example.com:8080/
2019-05-25 14:25:29,730: root/INFO: Download speed: 109.07 Mbps, 383.08 MiB received in 37 downloads (38 raw requests)
2019-05-25 14:25:29,732: root/INFO: Testing upload speed to http://example.com:8080/
2019-05-25 14:26:15,136: root/INFO: Upload speed: 11.27 Mbps, 57.99 MiB sent in 49 uploads (99 raw requests)
```
