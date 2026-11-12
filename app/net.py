"""Small HTTP utilities (standard library only)."""

import json
import urllib.error
import urllib.request

USER_AGENT = "Survival-AI/1.0"

# Local services must never use the system proxy.
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _is_local(url):
    return any(h in url for h in ("://127.0.0.1", "://localhost", "://[::1]", "://0.0.0.0"))


def open_url(url, data=None, headers=None, timeout=10, method=None):
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    if data is not None and not isinstance(data, (bytes, bytearray)):
        data = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    if _is_local(url):
        return _LOCAL_OPENER.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def get_text(url, timeout=10):
    with open_url(url, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")


def get_json(url, timeout=10):
    return json.loads(get_text(url, timeout=timeout))


def is_up(url, timeout=1.5):
    try:
        with open_url(url, timeout=timeout) as r:
            return 200 <= r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False
