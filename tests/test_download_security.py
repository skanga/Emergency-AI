"""Transport downgrade and installer digest regressions (no network)."""
import contextlib
import hashlib
import io
from email.message import Message
from pathlib import Path
import tempfile
import unittest
import urllib.request
import urllib.response
from unittest.mock import patch

from app import downloads, prepare


class DownloadSecurityTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(downloads.time, 'sleep'))
        self.dest = str(self.root / 'archive')

    def test_rejects_non_https_before_transport_or_cached_reuse(self):
        Path(self.dest).write_bytes(b'old')
        with patch.object(downloads.subprocess, 'call') as curl, \
                patch.object(downloads, '_download_urllib') as fallback:
            for url in ('http://example.invalid/a', 'ftp://example.invalid/a', 'file:///tmp/a'):
                with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'HTTPS'):
                    downloads.download(url, self.dest, expected_size=3)
            curl.assert_not_called()
            fallback.assert_not_called()

    def test_curl_restricts_protocols_and_bounds_stalls(self):
        def transfer(cmd):
            for flag, value in (('--proto', '=https'), ('--proto-redir', '=https'),
                                ('--connect-timeout', '30'), ('--speed-time', '60'),
                                ('--speed-limit', '1')):
                self.assertIn(flag, cmd)
                self.assertEqual(cmd[cmd.index(flag) + 1], value)
            Path(self.dest + '.part').write_bytes(b'new')
            return 0
        with patch.object(downloads.shutil, 'which', return_value='curl'), \
                patch.object(downloads.subprocess, 'call', side_effect=transfer):
            downloads.download('https://example.invalid/a', self.dest, expected_size=3, retries=1)
        self.assertEqual(Path(self.dest).read_bytes(), b'new')

    def test_urllib_redirect_policy_including_after_curl_failure(self):
        for target, allowed in (('http://cdn.invalid/a', False), ('https://cdn.invalid/a', True)):
            with self.subTest(target=target):
                Path(self.dest).unlink(missing_ok=True)
                seen = []
                def response(req):
                    seen.append(req.full_url)
                    headers = Message()
                    if len(seen) == 1:
                        headers['Location'] = target
                        code, body = 302, b''
                    else:
                        code, body = 200, b'new'
                        headers['Content-Length'] = '3'
                    result = urllib.response.addinfourl(io.BytesIO(body), headers, req.full_url, code)
                    result.msg = 'test'
                    return result
                with patch.object(downloads.shutil, 'which', return_value='curl'), \
                        patch.object(downloads.subprocess, 'call', return_value=1), \
                        patch.object(urllib.request, '_opener', None), \
                        patch.object(urllib.request.HTTPSHandler, 'https_open', side_effect=response), \
                        patch.object(urllib.request.HTTPHandler, 'http_open', side_effect=response):
                    if allowed:
                        downloads.download('https://origin.invalid/a', self.dest, expected_size=3, retries=1)
                        self.assertEqual(Path(self.dest).read_bytes(), b'new')
                    else:
                        with self.assertRaises((ValueError, RuntimeError)):
                            downloads.download('https://origin.invalid/a', self.dest, expected_size=3, retries=1)
                        self.assertEqual(seen, ['https://origin.invalid/a'])
                        self.assertFalse(Path(self.dest).exists())

    def test_same_size_wrong_hash_never_replaces_existing_file(self):
        Path(self.dest).write_bytes(b'old')
        def transfer(cmd):
            Path(self.dest + '.part').write_bytes(b'bad')
            return 0
        with patch.object(downloads.shutil, 'which', return_value='curl'), \
                patch.object(downloads.subprocess, 'call', side_effect=transfer):
            with self.assertRaisesRegex(RuntimeError, 'sha256 mismatch'):
                downloads.download('https://example.invalid/a', self.dest, expected_size=3,
                                   sha256=hashlib.sha256(b'new').hexdigest(), retries=1)
        self.assertEqual(Path(self.dest).read_bytes(), b'old')
        self.assertFalse(Path(self.dest + '.part').exists())


class InstallerDigestTests(unittest.TestCase):
    def test_python_and_llama_propagate_digest_and_reject_missing_or_invalid(self):
        for component in ('python', 'llama'):
            for digest in ('sha256:' + 'a' * 64, None, '', 'sha256:bad', 'md5:' + 'a' * 64):
                with self.subTest(component=component, digest=digest), tempfile.TemporaryDirectory() as root:
                    name = ('cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only.tar.gz'
                            if component == 'python' else 'llama-b123-bin-ubuntu-x64.tar.gz')
                    release = {'tag_name': 'b123', 'assets': [
                        {'name': name, 'browser_download_url': 'https://example.invalid/a',
                         'size': 3, 'digest': digest}]}
                    metadata = release if component == 'python' else [release]
                    with patch.object(prepare, 'RUNTIME_DIR', root), \
                            patch.object(prepare, 'get_json', return_value=metadata), \
                            patch.object(prepare, 'download', side_effect=RuntimeError('stop before extraction')) as fetch, \
                            contextlib.redirect_stdout(io.StringIO()) as output:
                        result = getattr(prepare, 'get_' + component)('linux-x86_64', prepare.T['en'])
                    self.assertFalse(result)
                    if digest == 'sha256:' + 'a' * 64:
                        self.assertEqual(fetch.call_args.kwargs.get('sha256'), 'a' * 64)
                    else:
                        fetch.assert_not_called()
                        self.assertIn('SHA-256', output.getvalue())

    def test_invalid_cuda_companion_digest_prevents_either_download(self):
        with tempfile.TemporaryDirectory() as root, \
                patch.object(prepare, 'RUNTIME_DIR', root), \
                patch.object(prepare, 'download') as fetch, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(prepare._install_llama(
                'windows-x86_64', prepare.T['en'], 'b123',
                ('engine.zip', 'https://example.invalid/engine', 3, 'sha256:' + 'a' * 64),
                'cuda', ('runtime.zip', 'https://example.invalid/runtime', 3, None)))
            fetch.assert_not_called()
            self.assertIn('SHA-256', output.getvalue())
