"""Local web server (standard library only): UI and API."""

import json
import mimetypes
import os
import posixpath
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .config import LANGS, WEB_DIR
from .net import open_url

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


def make_handler(engine, settings):
    class Handler(BaseHTTPRequestHandler):
        server_version = "IA-da-Sobrevivencia/" + __version__

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
                if path == "/api/guides":
                    return self._send(200, engine.kb.list_docs(self._lang(q)))
                if path == "/api/guide":
                    md = engine.kb.get_doc(self._lang(q), q.get("id", ""))
                    if md is None:
                        return self._send(404, {"error": "not found"})
                    return self._send(200, {"id": q.get("id"), "markdown": md})
                if path == "/api/search":
                    lang = self._lang(q)
                    res = [ch.to_dict(score=s, max_chars=400)
                           for s, ch in engine.kb.search(q.get("q", ""), lang, k=int(q.get("k", 10)))]
                    return self._send(200, res)
                if path.startswith("/kiwix/"):
                    return self._proxy_kiwix(path[len("/kiwix"):], urllib.parse.urlparse(self.path).query)
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
            rel = posixpath.normpath(urllib.parse.unquote(path)).lstrip("/")
            full = os.path.realpath(os.path.join(WEB_DIR, rel))
            if not full.startswith(os.path.realpath(WEB_DIR)) or not os.path.isfile(full):
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
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(400, {"error": "invalid json"})
            if path == "/api/ask":
                return self._ask_stream(body)
            return self._send(404, {"error": "not found"})

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


def serve(engine, settings, host=None, port=None):
    host = host or settings.get("web_host", "127.0.0.1")
    port = int(port or settings.get("web_port", 8090))
    httpd = ThreadingHTTPServer((host, port), make_handler(engine, settings))
    httpd.daemon_threads = True
    return httpd
