"""Space checks use incremental writes on the destination filesystem."""
import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import tarfile
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from app import prepare


class DiskSpaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dest = str(self.root / 'model')
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(patch.object(prepare.shutil, 'which', return_value=None))
        self.real_urllib = prepare._download_urllib
        stack.enter_context(patch.object(prepare, '_download_urllib', return_value=False))

    def test_complete_verified_file_needs_no_additional_space(self):
        Path(self.dest).write_bytes(b'complete')
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)), \
                patch.object(prepare, '_download_urllib') as fetch:
            prepare.download('https://example.invalid/model', self.dest, expected_size=8,
                             sha256=hashlib.sha256(b'complete').hexdigest())
        fetch.assert_not_called()

    def test_insufficient_space_stops_before_network(self):
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)), \
                patch.object(prepare, '_download_urllib') as fetch:
            with self.assertRaisesRegex(OSError, 'Insufficient disk space'):
                prepare.download('https://example.invalid/model', self.dest, expected_size=10**8)
        fetch.assert_not_called()

    def test_resume_counts_only_missing_bytes(self):
        part = Path(self.dest + '.part')
        with part.open('wb') as stream:
            stream.truncate(8 * 1024**2)
        def fetch(*args):
            with part.open('ab') as stream:
                stream.truncate(10 * 1024**2)
            return True
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=3*1024**2)), \
                patch.object(prepare.shutil, 'which', return_value=None), \
                patch.object(prepare, '_download_urllib', side_effect=fetch):
            prepare.download('https://example.invalid/model', self.dest, expected_size=10*1024**2)

    def test_replacement_keeps_old_file_and_requires_space_for_new_file(self):
        Path(self.dest).write_bytes(b'old')
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            with self.assertRaises(OSError):
                prepare.download('https://example.invalid/model', self.dest, expected_size=10**8)
        self.assertEqual(Path(self.dest).read_bytes(), b'old')

    def test_extraction_checks_uncompressed_size_before_writing(self):
        archive = self.root / 'runtime.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr('runtime/binary', b'x' * (2 * 1024**2))
        destination = self.root / 'staging'
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**2)) as disk:
            with self.assertRaisesRegex(OSError, 'Insufficient disk space'):
                prepare.extract(str(archive), str(destination))
        self.assertFalse((destination / 'runtime/binary').exists())
        self.assertEqual(Path(disk.call_args.args[0]), destination)

    def test_tar_extraction_checks_uncompressed_size(self):
        archive = self.root / 'runtime.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            member = tarfile.TarInfo('binary')
            member.size = 2 * 1024**2
            output.addfile(member, io.BytesIO(b'x' * member.size))
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**2)):
            with self.assertRaises(prepare.InsufficientSpaceError):
                prepare.extract(str(archive), str(self.root / 'staging'))

    @unittest.skipUnless(os.name == 'nt', 'Windows materializes symbolic links')
    def test_windows_link_copies_count_toward_extraction_space(self):
        archive = self.root / 'runtime.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            member = tarfile.TarInfo('binary')
            member.size = 300000
            output.addfile(member, io.BytesIO(b'x' * member.size))
            alias = tarfile.TarInfo('alias')
            alias.type = tarfile.SYMTYPE
            alias.linkname = 'binary'
            output.addfile(alias)
        with patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=550000)):
            with self.assertRaises(prepare.InsufficientSpaceError):
                prepare.extract(str(archive), str(self.root / 'staging'))

    def test_unknown_size_response_checked_before_writing(self):
        response = io.BytesIO(b'x')
        response.headers = {'Content-Length': '10000000'}
        response.status = 200
        # Call the real fallback rather than the setup network stub.
        original = self.real_urllib
        with patch.object(prepare.urllib.request, 'urlopen', return_value=response), \
                patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            with self.assertRaises(prepare.InsufficientSpaceError):
                original('https://example.invalid/model', self.dest + '.part', 1)
        self.assertFalse(Path(self.dest + '.part').exists())
