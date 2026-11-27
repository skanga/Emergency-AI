"""Kiwix proxy transport preserves browser behavior without whole-body buffers."""
import http.client
import io
import threading
import unittest
import urllib.error
from unittest.mock import Mock, patch

from app import server


class BoundedBody(io.BytesIO):
    def read(self, size=-1):
        if not 0 < size <= 65536:
            raise AssertionError('unbounded upstream read')
        return super().read(size)

    def read1(self, size=-1):
        return self.read(size)


class KiwixProxyTests(unittest.TestCase):
    def setUp(self):
        self.engine = Mock()
        self.engine.kiwix.base_url = 'http://127.0.0.1:8092'
        self.httpd = server.serve(self.engine, {}, '127.0.0.1', 0)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def response(self, body=b'body', status=200, headers=None):
        response = BoundedBody(body)
        response.status = status
        response.headers = headers or {'Content-Type': 'text/html'}
        return response

    def request(self, path='/kiwix/content/book/article', method='GET', headers=None):
        connection = http.client.HTTPConnection(*self.httpd.server_address, timeout=3)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_streams_large_body_with_same_origin_redirect_guard(self):
        body = b'x' * (1024 * 1024 + 7)
        with patch.object(server, 'open_url', return_value=self.response(body)) as fetch:
            code, headers, actual = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(actual, body)
        self.assertEqual(fetch.call_args.kwargs.get('allowed_origin'), self.engine.kiwix.base_url)
        self.assertNotIn('Content-Security-Policy', headers)

    def test_range_and_representation_headers_are_preserved(self):
        upstream = {'Content-Type': 'video/mp4', 'Content-Length': '3',
                    'Content-Range': 'bytes 3-5/20', 'Accept-Ranges': 'bytes',
                    'ETag': '"version"', 'Content-Disposition': 'inline; filename="movie.mp4"'}
        with patch.object(server, 'open_url', return_value=self.response(b'abc', 206, upstream)) as fetch:
            code, headers, body = self.request(headers={'Range': 'bytes=3-5', 'If-Range': '"version"'})
        self.assertEqual((code, body), (206, b'abc'))
        for key, value in upstream.items():
            self.assertEqual(headers.get(key), value)
        self.assertEqual(fetch.call_args.kwargs['headers']['Range'], 'bytes=3-5')
        self.assertEqual(fetch.call_args.kwargs['headers']['If-Range'], '"version"')

    def test_upstream_errors_keep_status_headers_and_body(self):
        for status in (404, 416, 503):
            with self.subTest(status=status):
                error = urllib.error.HTTPError('http://127.0.0.1:8092/a', status, 'upstream',
                        {'Content-Type': 'text/html', 'Content-Range': 'bytes */20', 'Retry-After': '5'},
                        BoundedBody(b'upstream error'))
                with patch.object(server, 'open_url', side_effect=error):
                    code, headers, body = self.request()
                self.assertEqual((code, body), (status, b'upstream error'))
                self.assertEqual(headers.get('Retry-After'), '5')
                self.assertTrue(error.closed)

    def test_head_forwards_head_and_does_not_read_body(self):
        response = self.response(headers={'Content-Type': 'application/pdf', 'Content-Length': '123456'})
        with patch.object(response, 'read', side_effect=AssertionError('HEAD read body')), \
                patch.object(server, 'open_url', return_value=response) as fetch:
            code, headers, body = self.request(method='HEAD')
        self.assertEqual((code, body), (200, b''))
        self.assertEqual(headers.get('Content-Length'), '123456')
        self.assertEqual(fetch.call_args.kwargs.get('method'), 'HEAD')

    def test_invalid_length_uses_close_delimited_stream(self):
        with patch.object(server, 'open_url', return_value=self.response(b'abc', headers={
                'Content-Type': 'text/plain', 'Content-Length': 'bad'})):
            code, headers, body = self.request()
        self.assertEqual((code, body), (200, b'abc'))
        self.assertNotIn('Content-Length', headers)

    def test_script_and_style_types_are_preserved_without_blocking_csp(self):
        for path, ctype in (('/skin/main.js', 'application/javascript'),
                            ('/skin/main.css', 'text/css'), ('/content/book/a.svg', 'image/svg+xml')):
            with self.subTest(path=path), patch.object(server, 'open_url',
                    return_value=self.response(b'asset', headers={'Content-Type': ctype})):
                code, headers, body = self.request(path)
                self.assertEqual((code, body), (200, b'asset'))
                self.assertEqual(headers['Content-Type'], ctype)
                self.assertNotIn('Content-Security-Policy', headers)

    def test_real_redirects_follow_only_the_configured_kiwix_origin(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        calls = []
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                calls.append(self.path)
                if self.path == '/content/local':
                    self.send_response(302)
                    self.send_header('Location', '/content/final')
                elif self.path == '/content/external':
                    self.send_response(302)
                    self.send_header('Location', 'http://127.0.0.1:1/forbidden')
                else:
                    self.send_response(200)
                self.end_headers()
                self.wfile.write(b'article')
        upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        self.addCleanup(upstream.server_close)
        self.addCleanup(upstream.shutdown)
        self.engine.kiwix.base_url = 'http://127.0.0.1:' + str(upstream.server_port)
        code, headers, body = self.request('/content/local')
        self.assertEqual(code, 302)
        self.assertEqual(headers.get('Location'), '/content/final')
        self.assertEqual(self.request(headers['Location'])[::2], (200, b'article'))
        code, headers, body = self.request('/content/external')
        self.assertEqual(code, 502)
        self.assertIn(b'outside the configured service', body)
        self.assertEqual(calls, ['/content/local', '/content/final', '/content/external'])

    def test_conditional_request_preserves_not_modified_response(self):
        error = urllib.error.HTTPError('http://127.0.0.1:8092/a', 304, 'not modified',
                                       {'ETag': '"version"'}, BoundedBody(b''))
        with patch.object(server, 'open_url', side_effect=error) as fetch:
            code, headers, body = self.request(headers={'If-None-Match': '"version"'})
        self.assertEqual((code, body), (304, b''))
        self.assertEqual(headers['ETag'], '"version"')
        self.assertEqual(fetch.call_args.kwargs['headers']['If-None-Match'], '"version"')

    def test_transport_failure_before_headers_returns_gateway_error(self):
        with patch.object(server, 'open_url', side_effect=TimeoutError('stalled')):
            self.assertEqual(self.request()[0], 502)

    def test_failure_after_headers_does_not_append_another_response(self):
        response = self.response()
        with patch.object(response, 'read', side_effect=[b'partial', TimeoutError('stalled')]), \
                patch.object(server, 'open_url', return_value=response):
            code, headers, body = self.request()
        self.assertEqual((code, body), (200, b'partial'))
