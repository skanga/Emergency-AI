"""Test servers: an OpenAI-compatible LLM and a minimal kiwix-serve."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><name>teste_medicina_pt</name><title>Medicina de Teste</title><language>por</language></entry>
</feed>"""

SEARCH = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>Desidratação</title><link>/content/teste_medicina_pt/A/Desidratacao</link>
  <description>A &lt;b&gt;desidratação&lt;/b&gt; é a perda excessiva de água...</description></item>
</channel></rss>"""

ARTICLE = """<html><body><h1>Desidratação</h1>
<p>A desidratação ocorre quando o corpo perde mais água do que recebe, comum na diarreia.</p>
<p>O tratamento principal da desidratação leve é a solução de reidratação oral em pequenos goles.</p>
<script>var x=1;</script></body></html>"""


class LLMHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            body = json.dumps({"data": [{"id": "modelo-teste.gguf"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(length))
        LLMHandler.last_request = req
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ["Ferva a água ", "por 1 minuto [1]. ", "Depois use o soro [2]."]:
            chunk = {"choices": [{"delta": {"content": piece}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


class KiwixHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        body = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/catalog/v2/entries"):
            return self._send(CATALOG, "application/atom+xml")
        if u.path == "/search":
            q = parse_qs(u.query)
            assert q.get("format") == ["xml"]
            return self._send(SEARCH, "application/rss+xml")
        if u.path.startswith("/content/"):
            return self._send(ARTICLE, "text/html")
        self.send_response(404)
        self.end_headers()


def start(handler, port):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
