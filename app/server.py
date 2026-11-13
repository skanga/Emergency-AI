"""Local web server (standard library only): UI and API."""

import json
import mimetypes
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer

from . import __version__
from .config import LANGS, WEB_DIR
from .net import open_url

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

MAX_BODY = 64 * 1024


class BoundedHTTPServer(ThreadingHTTPServer):
    """Bound open request threads as well as the more expensive answer stream."""
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def server_bind(self):
        # HTTPServer's default reverse-DNS lookup can stall offline startup.
        # This app only needs the bound address, not a resolved server name.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nRetry-After: 2\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def make_handler(engine, settings, models=None):
    answer_slot = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        server_version = "Emergency-AI/" + __version__
        timeout = 15

        def log_message(self, fmt, *args):  # quiet
            pass

        # ---------- helpers ----------
        def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Emergency-AI-Bind", self.server.server_address[0])
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _query(self):
            parsed = urllib.parse.urlparse(self.path)
            return parsed.path, {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        def _lang(self, q):
            lang = q.get("lang", settings.get("language", "en"))
            return lang if lang in LANGS else "en"

        # ---------- GET ----------
        def do_GET(self):
            path, q = self._query()
            try:
                if path == "/api/status":
                    st = engine.status()
                    st.update({"version": __version__, "language": settings.get("language", "en")})
                    return self._send(200, st)
                if path == "/api/models":
                    state = models.status() if models else {"enabled": False, "reason": "disabled", "models": []}
                    return self._send(200, state)
                if path == "/api/guides":
                    return self._send(200, engine.kb.list_docs(self._lang(q)))
                if path == "/api/guide":
                    md = engine.kb.get_doc(self._lang(q), q.get("id", ""))
                    if md is None:
                        return self._send(404, {"error": "not found"})
                    return self._send(200, {"id": q.get("id"), "markdown": md})
                if path == "/api/search":
                    lang = self._lang(q)
                    try:
                        limit = int(q.get("k", 10))
                    except ValueError:
                        return self._send(400, {"error": "invalid search limit"})
                    if not 1 <= limit <= 50 or len(q.get("q", "")) > 2000:
                        return self._send(400, {"error": "invalid search parameters"})
                    res = [ch.to_dict(score=s, max_chars=400)
                           for s, ch in engine.kb.search(q.get("q", ""), lang, k=limit)]
                    return self._send(200, res)
                if path.startswith("/kiwix/"):
                    return self._proxy_kiwix(path[len("/kiwix"):], urllib.parse.urlparse(self.path).query)
                # Kiwix HTML uses root-relative links for articles, scripts and styles.
                if path.split("/", 2)[1] in ("content", "skin", "raw", "viewer", "search", "suggest", "catalog", "catch", "random"):
                    return self._proxy_kiwix(path, urllib.parse.urlparse(self.path).query)
                return self._static(path)
            except BrokenPipeError:
                pass
            except Exception as e:  # pragma: no cover
                try:
                    self._send(500, {"error": str(e)})
                except Exception:
                    pass

        def _static(self, path):
            if path in ("", "/"):
                path = "/index.html"
            rel = urllib.parse.unquote(path).lstrip("/")
            if "\\" in rel or ":" in rel or "\0" in rel:
                return self._send(404, {"error": "not found"})
            root = os.path.realpath(WEB_DIR)
            full = os.path.realpath(os.path.join(root, rel))
            if os.path.commonpath([root, full]) != root or not os.path.isfile(full):
                return self._send(404, {"error": "not found"})
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                self._send(200, f.read(), ctype)

        def _proxy_kiwix(self, subpath, query):
            """Allow Kiwix articles to open when another device on the network accesses the UI."""
            url = engine.kiwix.base_url + subpath + ("?" + query if query else "")
            try:
                with open_url(url, timeout=15) as r:
                    body = r.read()
                    ctype = r.headers.get("Content-Type", "text/html")
                    self._send(r.status, body, ctype)
            except Exception as e:
                self._send(502, {"error": "kiwix: " + str(e)})

        # ---------- POST ----------
        def do_POST(self):
            path, q = self._query()
            if path not in ("/api/ask", "/api/models"):
                return self._send(404, {"error": "not found"})
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self._send(403, {"error": "foreign origin"})
            if self.headers.get_content_type() != "application/json":
                return self._send(415, {"error": "expected application/json"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "invalid Content-Length"})
            if length < 0 or self.headers.get("Transfer-Encoding"):
                return self._send(400, {"error": "invalid request framing"})
            if length > MAX_BODY:
                return self._send(413, {"error": "request body too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(400, {"error": "invalid json"})
            except TimeoutError:
                return self._send(408, {"error": "request timed out"})
            if path == "/api/models":
                if not isinstance(body, dict) or not isinstance(body.get("model"), str):
                    return self._send(400, {"error": "model must be a filename"})
                if models is None:
                    return self._send(409, {"error": "model switching is disabled"})
                try:
                    return self._send(202, models.request(body["model"]))
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                except RuntimeError as e:
                    return self._send(409, {"error": str(e)})
            if not isinstance(body, dict) or not isinstance(body.get("q"), str):
                return self._send(400, {"error": "q must be a string"})
            history = body.get("history", [])
            if (len(body["q"]) > 2000 or not isinstance(history, list) or len(history) > 8
                    or any(not isinstance(h, dict) or h.get("role") not in ("user", "assistant")
                           or not isinstance(h.get("content"), str) or len(h["content"]) > 16000
                           for h in history)
                    or any(k in body and not isinstance(body[k], bool) for k in ("use_llm", "use_kiwix"))
                    or ("lang" in body and body["lang"] not in LANGS)):
                return self._send(400, {"error": "invalid question, history or options"})
            acquired = models.begin_answer() if models else answer_slot.acquire(blocking=False)
            if not acquired:
                return self._send(503, {"error": "another answer or model switch is in progress"}, extra={"Retry-After": "2"})
            try:
                return self._ask_stream(body)
            finally:
                if models:
                    models.end_answer()
                else:
                    answer_slot.release()

        def _ask_stream(self, body):
            question = (body.get("q") or "").strip()[:2000]
            lang = body.get("lang") if body.get("lang") in LANGS else settings.get("language", "en")
            if not question:
                return self._send(400, {"error": "empty question"})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            def emit(event, data):
                payload = json.dumps(data, ensure_ascii=False)
                self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()

            try:
                for kind, data in engine.answer(
                    question, lang,
                    history=body.get("history") or [],
                    use_kiwix=body.get("use_kiwix", True),
                    use_llm=body.get("use_llm", True),
                ):
                    emit(kind, data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    emit("error", {"error": str(e)})
                except Exception:
                    pass

    return Handler


def serve(engine, settings, host=None, port=None, models=None):
    host = host or settings.get("web_host", "0.0.0.0")
    port = int(settings.get("web_port", 8090) if port is None else port)
    httpd = BoundedHTTPServer((host, port), make_handler(engine, settings, models))
    httpd.daemon_threads = True
    return httpd
