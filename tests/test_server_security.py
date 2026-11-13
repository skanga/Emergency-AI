"""HTTP boundary regressions, using actual requests and temporary files."""

import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from app import server


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "web").mkdir()
        (root / "web" / "index.html").write_text("home", encoding="utf-8")
        (root / "web-private").mkdir()
        (root / "web-private" / "secret.txt").write_text("secret", encoding="utf-8")
        self.patch = patch.object(server, "WEB_DIR", str(root / "web"))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.engine = Mock()
        self.engine.answer.return_value = iter([("done", {"mode": "search"})])
        self.httpd = server.serve(self.engine, {}, "127.0.0.1", 0)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, path="/api/ask", body=b'{"q":"hello"}', headers=None, method="POST"):
        conn = http.client.HTTPConnection(*self.httpd.server_address, timeout=3)
        try:
            conn.request(method, path, body, headers or {"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_encoded_backslash_cannot_escape_web_root(self):
        code, body = self.request("/%2e%2e%5cweb-private%5csecret.txt", body=None, method="GET")
        self.assertEqual(code, 404)
        self.assertNotIn(b"secret", body)

    def test_valid_request_still_streams(self):
        code, body = self.request()
        self.assertEqual(code, 200)
        self.assertIn(b"event: done", body)

    def test_invalid_json_shapes_are_client_errors(self):
        for value in ([], None, {"q": 123}, {"q": "x", "history": "bad"},
                      {"q": "x", "history": [1]}, {"q": "x", "history": [{"role": "user", "content": []}]},
                      {"q": "x", "use_llm": "false"}, {"q": "x" * 2001}):
            with self.subTest(value=value):
                self.assertEqual(self.request(body=json.dumps(value).encode())[0], 400)

    def test_oversized_body_rejected(self):
        self.assertEqual(self.request(body=b"", headers={"Content-Type": "application/json", "Content-Length": "70000"})[0], 413)

    def test_invalid_content_length_rejected(self):
        for length in ("no", "-1"):
            with self.subTest(length=length):
                self.assertEqual(self.request(headers={"Content-Type": "application/json", "Content-Length": length})[0], 400)

    def test_foreign_origin_rejected(self):
        self.assertEqual(self.request(headers={"Content-Type": "application/json", "Origin": "https://untrusted.example"})[0], 403)

    def test_wrong_media_type_rejected(self):
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 415)

    def test_bad_search_limit_is_client_error(self):
        for value in ("oops", "-1", "100000"):
            self.assertEqual(self.request("/api/search?q=water&k=" + value, None, method="GET")[0], 400)

    def test_busy_inference_returns_retryable_status(self):
        started, finish = threading.Event(), threading.Event()

        def answer(*args, **kwargs):
            started.set()
            finish.wait(3)
            yield "done", {}

        self.engine.answer.side_effect = answer
        worker = threading.Thread(target=self.request)
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            self.assertEqual(self.request()[0], 503)
        finally:
            finish.set()
            worker.join(4)

    def test_kiwix_root_relative_article_resources_are_proxied(self):
        self.engine.kiwix.base_url = "http://127.0.0.1:8092"
        for path in ("/content/book/image.png", "/skin/style.css", "/viewer", "/search?pattern=water"):
            response = io.BytesIO(b"kiwix resource")
            response.status = 200
            response.headers = {"Content-Type": "text/plain"}
            with self.subTest(path=path), patch.object(server, "open_url", return_value=response) as fetch:
                code, body = self.request(path, None, method="GET")
                self.assertEqual(code, 200)
                self.assertEqual(body, b"kiwix resource")
                self.assertEqual(fetch.call_args.args[0], "http://127.0.0.1:8092" + path)
