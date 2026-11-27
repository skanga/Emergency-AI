"""Proxy routing and bounded HTTP response regressions."""
import io
import unittest
from unittest.mock import Mock, patch

from app import net


class ProxyRoutingTests(unittest.TestCase):
    def test_only_exact_local_hosts_bypass_proxy(self):
        local = ('http://127.0.0.1:8091/a', 'http://localhost/a',
                 'https://LOCALHOST:8092/a', 'http://[::1]:8091/a', 'http://0.0.0.0/a')
        external = ('https://127.0.0.1.evil.com/a', 'https://localhost.evil.com/a',
                    'https://evil.com/?r=://localhost', 'https://evil.com/path/://127.0.0.1',
                    'https://localhost@evil.com/a', 'https://0.0.0.0.evil.com/a')
        for url in local + external:
            with self.subTest(url=url), patch.object(net._LOCAL_OPENER, 'open') as direct, \
                    patch.object(net.urllib.request, 'urlopen') as proxied:
                net.open_url(url)
                self.assertEqual(direct.call_count, int(url in local))
                self.assertEqual(proxied.call_count, int(url in external))

    def test_origin_restricted_requests_use_same_host_decision(self):
        for url, local in (('http://localhost:8092/a', True),
                           ('https://localhost.evil.com/a', False)):
            with self.subTest(url=url), patch.object(net.urllib.request, 'build_opener') as build:
                net.open_url(url, allowed_origin=url)
                handlers = build.call_args.args
                self.assertTrue(any(isinstance(h, net.SameOriginRedirectHandler) for h in handlers))
                self.assertEqual(any(isinstance(h, net.urllib.request.ProxyHandler) for h in handlers), local)


class ResponseLengthTests(unittest.TestCase):
    def response(self, body, length):
        response = io.BytesIO(body)
        response.headers = {} if length is None else {'Content-Length': length}
        return response

    def test_unknown_or_invalid_lengths_allow_bounded_body(self):
        for length in (None, '', 'garbage', '3, 3', '-1'):
            with self.subTest(length=length):
                self.assertEqual(net._read_response(self.response(b'abc', length), 3, None), b'abc')

    def test_streaming_limit_holds_for_invalid_or_understated_lengths(self):
        for length in (None, '', 'garbage', '3, 3', '-1', '1'):
            with self.subTest(length=length), self.assertRaises(net.ResponseTooLarge):
                net._read_response(self.response(b'abcd', length), 3, None)

    def test_valid_oversized_header_rejects_before_reading(self):
        response = Mock(headers={'Content-Length': '4'})
        with self.assertRaises(net.ResponseTooLarge):
            net._read_response(response, 3, None)
        response.read.assert_not_called()
        response.read1.assert_not_called()

    def test_valid_exact_length_is_accepted(self):
        self.assertEqual(net._read_response(self.response(b'abc', '3'), 3, None), b'abc')
