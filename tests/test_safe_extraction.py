"""Archive safety must not depend on tarfile extraction-filter availability."""
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app import downloads, upgrade_assets


class SafeExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dest = self.root / 'out'

    def tar(self, entries):
        archive = self.root / 'input.tar'
        with tarfile.open(archive, 'w') as stream:
            for name, kind, target in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                if kind == tarfile.REGTYPE:
                    member.size = 4
                    stream.addfile(member, io.BytesIO(b'data'))
                else:
                    member.linkname = target
                    stream.addfile(member)
        return archive

    def test_tar_bad_names_rejected_without_filters_before_any_file_is_written(self):
        original = tarfile.TarFile.extractall
        def legacy(stream, path, members=None, **kwargs):
            if 'filter' in kwargs:
                raise TypeError('legacy API')
            return original(stream, path, members=members, filter='fully_trusted')
        for name in ('../escape', '/absolute', 'C:/drive', 'dir\\escape'):
            with self.subTest(name=name):
                archive = self.tar([('good', tarfile.REGTYPE, ''), (name, tarfile.REGTYPE, '')])
                with patch.object(tarfile.TarFile, 'extractall', legacy), self.assertRaises(ValueError):
                    downloads.extract(str(archive), str(self.dest))
                self.assertFalse((self.dest / 'good').exists())

    def test_tar_rejects_escaping_links_special_files_and_link_parent(self):
        cases = [ [('link', kind, '../outside')] for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) ]
        cases += [[('fifo', tarfile.FIFOTYPE, '')],
                  [('dir', tarfile.SYMTYPE, 'real'), ('dir/data', tarfile.REGTYPE, ''),
                   ('real', tarfile.DIRTYPE, '')]]
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                downloads.extract(str(self.tar(entries)), str(self.dest))

    def test_zip_rejects_bad_paths_and_symlink_metadata_before_writes(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'dir\\escape', 'link'):
            archive = self.root / 'input.zip'
            with zipfile.ZipFile(archive, 'w') as stream:
                stream.writestr('good', b'data')
                member = zipfile.ZipInfo(name)
                # Write the hostile name verbatim, even on Windows.
                member.filename = name
                if name == 'link':
                    member.create_system = 3
                    member.external_attr = 0o120777 << 16
                stream.writestr(member, b'data')
            with self.subTest(name=name), self.assertRaises(ValueError):
                downloads.extract(str(archive), str(self.dest))
            self.assertFalse((self.dest / 'good').exists())

    def test_zip_validates_original_names_before_platform_normalization(self):
        for name in ('dir\\escape', 'file\0hidden'):
            with self.subTest(name=name):
                archive = self.root / 'raw.zip'
                with zipfile.ZipFile(archive, 'w') as stream:
                    member = zipfile.ZipInfo(name)
                    member.filename = name
                    stream.writestr(member, b'data')
                # Reproduce Windows ZipInfo normalization on every CI platform.
                with patch.object(zipfile.os, 'sep', '\\'):
                    with zipfile.ZipFile(archive) as stream:
                        member = stream.infolist()[0]
                        self.assertEqual(member.orig_filename, name)
                        self.assertNotEqual(member.filename, name)
                    with self.assertRaisesRegex(ValueError, 'archive path'):
                        downloads.extract(str(archive), str(self.dest))

    @unittest.skipIf(os.name == 'nt', 'Requires symlink privileges')
    def test_existing_file_and_directory_symlinks_are_rejected(self):
        self.dest.mkdir()
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'data').write_bytes(b'keep')
        (self.dest / 'alias').symlink_to(outside, target_is_directory=True)
        (self.dest / 'file').symlink_to(outside / 'data')
        for name in ('alias/data', 'file'):
            for kind in ('tar', 'zip'):
                archive = self.tar([(name, tarfile.REGTYPE, '')])
                if kind == 'zip':
                    archive = self.root / 'input.zip'
                    with zipfile.ZipFile(archive, 'w') as stream:
                        stream.writestr(name, b'data')
                with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                    downloads.extract(str(archive), str(self.dest))
                self.assertEqual((outside / 'data').read_bytes(), b'keep')

    @unittest.skipIf(os.name == 'nt', 'POSIX links')
    def test_safe_internal_links_survive_without_extraction_filters(self):
        archive = self.tar([('bin/alias', tarfile.SYMTYPE, '../lib/data'),
                            ('hard', tarfile.LNKTYPE, 'lib/data'), ('lib/data', tarfile.REGTYPE, '')])
        with patch.object(tarfile.TarFile, 'extractall', side_effect=TypeError('legacy API')):
            downloads.extract(str(archive), str(self.dest))
        self.assertTrue((self.dest / 'bin/alias').is_symlink())
        self.assertEqual((self.dest / 'bin/alias').read_bytes(), b'data')
        self.assertEqual((self.dest / 'hard').read_bytes(), b'data')

    @unittest.skipIf(os.name == 'nt', 'POSIX hard links')
    def test_existing_hard_link_cannot_modify_outside_file(self):
        self.dest.mkdir()
        outside = self.root / 'outside'; outside.write_bytes(b'keep')
        os.link(outside, self.dest / 'data')
        archive = self.tar([('data', tarfile.REGTYPE, '')])
        downloads.extract(str(archive), str(self.dest))
        self.assertEqual(outside.read_bytes(), b'keep')
        self.assertEqual((self.dest / 'data').read_bytes(), b'data')

    def test_cycles_and_duplicate_members_are_rejected(self):
        for entries in ([('a', tarfile.SYMTYPE, 'b'), ('b', tarfile.SYMTYPE, 'a')],
                        [('a', tarfile.REGTYPE, ''), ('a', tarfile.SYMTYPE, 'b')]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                downloads.extract(str(self.tar(entries)), str(self.dest))

    def test_upgrade_still_rejects_links_unless_materialized(self):
        archive = self.tar([('data', tarfile.REGTYPE, ''), ('alias', tarfile.SYMTYPE, 'data')])
        with self.assertRaises(ValueError):
            upgrade_assets._extract(archive, self.dest)
        upgrade_assets._extract(archive, self.dest, materialize_links=True)
        self.assertEqual((self.dest / 'alias').read_bytes(), b'data')
        self.assertFalse((self.dest / 'alias').is_symlink())
