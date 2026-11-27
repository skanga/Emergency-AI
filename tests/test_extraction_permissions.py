"""Extracted documentation and executables must respect caller permissions."""
import io
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
import zipfile

from app.downloads import extract


@unittest.skipIf(os.name == 'nt', 'POSIX permission bits')
class ExtractionPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dest = self.root / 'out'

    def unpack(self, archive, mask):
        previous = os.umask(mask)
        try:
            extract(str(archive), str(self.dest))
        finally:
            os.umask(previous)

    def mode(self, name):
        return stat.S_IMODE((self.dest / name).stat().st_mode)

    def zip(self):
        archive = self.root / 'tools.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name in ('LICENSE', 'README', 'bin/README', 'bin/llama-server',
                         'kiwix-serve', 'libexample.so', 'bin/custom-data'):
                z.writestr(name, b'data')
        return archive

    def test_zip_only_known_executables_gain_execution(self):
        self.unpack(self.zip(), 0o022)
        for name in ('LICENSE', 'README', 'bin/README', 'libexample.so', 'bin/custom-data'):
            self.assertEqual(self.mode(name), 0o644, name)
        for name in ('bin/llama-server', 'kiwix-serve'):
            self.assertEqual(self.mode(name), 0o755, name)

    def test_zip_respects_restrictive_and_execute_umasks(self):
        for mask, expected in ((0o077, 0o700), (0o111, 0o644)):
            with self.subTest(mask=mask):
                self.unpack(self.zip(), mask)
                self.assertEqual(self.mode('bin/llama-server'), expected)
                self.assertEqual(self.mode('README') & 0o111, 0)

    def test_tar_preserves_modes_without_promoting_documentation(self):
        archive = self.root / 'tools.tar'
        with tarfile.open(archive, 'w') as t:
            for name, mode in (('LICENSE', 0o600), ('bin/helper', 0o750), ('lib.so', 0o640)):
                item = tarfile.TarInfo(name); item.size = 4; item.mode = mode
                t.addfile(item, io.BytesIO(b'data'))
        self.unpack(archive, 0o022)
        self.assertEqual(self.mode('LICENSE'), 0o600)
        self.assertEqual(self.mode('bin/helper'), 0o750)
        self.assertEqual(self.mode('lib.so'), 0o640)
        self.unpack(archive, 0o077)
        self.assertEqual(self.mode('bin/helper'), 0o700)

    def test_permission_pass_ignores_preexisting_files_and_symlinks(self):
        self.dest.mkdir()
        target = self.root / 'outside'; target.write_bytes(b'keep'); target.chmod(0o600)
        (self.dest / 'llama-server').symlink_to(target)
        existing = self.dest / 'PRIVATE'; existing.write_bytes(b'keep'); existing.chmod(0o600)
        self.unpack(self.zip(), 0o022)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(self.mode('PRIVATE'), 0o600)

    def test_tar_symlink_does_not_promote_target(self):
        archive = self.root / 'links.tar'
        with tarfile.open(archive, 'w') as t:
            item = tarfile.TarInfo('payload'); item.size = 4; item.mode = 0o600
            t.addfile(item, io.BytesIO(b'data'))
            link = tarfile.TarInfo('llama-server'); link.type = tarfile.SYMTYPE; link.linkname = 'payload'
            t.addfile(link)
        self.unpack(archive, 0o022)
        self.assertEqual(self.mode('payload'), 0o600)
        self.assertTrue((self.dest / 'llama-server').is_symlink())
