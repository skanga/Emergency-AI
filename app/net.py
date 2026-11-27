"""Small HTTP utilities (standard library only)."""

import json
import time
import urllib.error
import urllib.request
import urllib.parse

USER_AGENT = "Emergency-AI/1.0"

# Local services must never use the system proxy.
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _is_local(url):
    return urllib.parse.urlsplit(url).hostname in ("127.0.0.1", "localhost", "::1", "0.0.0.0")


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, origin, follow_redirects=True):
        self.follow_redirects = follow_redirects
        self.origin = urllib.parse.urlsplit(origin)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme, target.netloc) != (self.origin.scheme, self.origin.netloc):
            raise ValueError('Redirect is outside the configured service')
        if not self.follow_redirects:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url, data=None, headers=None, timeout=10, method=None, allowed_origin=None, follow_redirects=True):
    if not follow_redirects and allowed_origin is None:
        raise ValueError("Preserving redirects requires an allowed origin")
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    if data is not None and not isinstance(data, (bytes, bytearray)):
        data = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    if allowed_origin is not None:
        handlers = [SameOriginRedirectHandler(allowed_origin, follow_redirects)]
        if _is_local(url):
            handlers.append(urllib.request.ProxyHandler({}))
        return urllib.request.build_opener(*handlers).open(req, timeout=timeout)
    if _is_local(url):
        return _LOCAL_OPENER.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


class ResponseTooLarge(ValueError):
    """The response exceeds the caller's byte limit."""


def _read_response(response, max_bytes, deadline):
    try:
        length = int(response.headers.get('Content-Length', ''))
    except ValueError:
        length = None
    if length is not None and length > max_bytes:
        raise ResponseTooLarge(f'Response exceeds {max_bytes} bytes')
    chunks, total = [], 0
    while True:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Request deadline exceeded')
            # urllib exposes the underlying socket here on HTTP responses.
            sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
            if sock is not None:
                sock.settimeout(remaining)
        reader = getattr(response, "read1", None) or response.read
        chunk = reader(min(65536, max_bytes + 1 - total))
        if not chunk:
            return b''.join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLarge(f'Response exceeds {max_bytes} bytes')
        chunks.append(chunk)


def _get(url, timeout, max_bytes, deadline, allowed_origin):
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
    if timeout <= 0:
        raise TimeoutError('Request deadline exceeded')
    with open_url(url, timeout=timeout, allowed_origin=allowed_origin) as response:
        return _read_response(response, max_bytes, deadline), response.headers.get_content_charset() or 'utf-8'


def get_bytes(url, timeout=10, max_bytes=8 * 1024 * 1024, deadline=None, allowed_origin=None):
    """Read a bounded response, including servers without Content-Length."""
    return _get(url, timeout, max_bytes, deadline, allowed_origin)[0]


def get_text(url, timeout=10, max_bytes=8 * 1024 * 1024, deadline=None, allowed_origin=None):
    raw, charset = _get(url, timeout, max_bytes, deadline, allowed_origin)
    return raw.decode(charset, errors='replace')


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
