"""Portable Python extraction and interrupted-install recovery."""

import contextlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from app import prepare


class PythonInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "python.tar.gz"
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, data in (("python/bin/python3.12", b"interpreter"),
                               ("python/share/terminfo/n/ncr260vt300wpp", b"terminal data")):
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o755
                archive.addfile(member, io.BytesIO(data))
            for name, target in (("python/bin/python3", "python3.12"),
                                 ("python/share/terminfo/N/NCR260VT300WPP", "../n/ncr260vt300wpp")):
                member = tarfile.TarInfo(name)
                member.type = tarfile.SYMTYPE
                member.linkname = target
                archive.addfile(member)
        self.dest = self.root / "runtime/python/linux-x86_64"

    @unittest.skipUnless(os.name == "nt", "Windows case-insensitive link regression")
    def test_windows_materializes_case_colliding_links_without_symlinks(self):
        prepare.extract(str(self.archive), str(self.dest))
        alias = self.dest / "python/share/terminfo/N/NCR260VT300WPP"
        self.assertFalse(alias.is_symlink())
        self.assertEqual(alias.read_bytes(), b"terminal data")
        interpreter = self.dest / "python/bin/python3"
        self.assertFalse(interpreter.is_symlink())
        self.assertEqual(interpreter.read_bytes(), b"interpreter")

    def install(self, fail=False):
        asset = "cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only.tar.gz"
        def fetch(url, destination, **kwargs):
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            Path(destination).write_bytes(self.archive.read_bytes())
        original_extract = prepare.extract
        def unpack(archive, destination):
            if fail:
                Path(destination, "python").mkdir(parents=True)
                raise OSError("interrupted extraction")
            original_extract(archive, destination)
        with patch.object(prepare, "RUNTIME_DIR", str(self.root / "runtime")), \
                patch.object(prepare, "github_latest_assets", return_value=("20261110", [(asset, "https://example.invalid/python", self.archive.stat().st_size)])), \
                patch.object(prepare, "download", side_effect=fetch) as download, \
                patch.object(prepare, "extract", side_effect=unpack), \
                contextlib.redirect_stdout(io.StringIO()):
            return prepare.get_python("linux-x86_64", prepare.T["en"]), download.call_count

    def test_partial_folder_is_repaired_and_completed_install_is_skipped(self):
        (self.dest / "python").mkdir(parents=True)
        (self.dest / "python/partial").write_bytes(b"incomplete")
        self.assertEqual(self.install(), (True, 1))
        self.assertFalse((self.dest / "python/partial").exists())
        self.assertTrue((self.dest / "python/bin/python3").is_file())
        self.assertTrue(json.loads((self.dest / "installation.json").read_text())["complete"])
        self.assertEqual(self.install(), (True, 0))

    def test_failed_extraction_preserves_previous_folder_and_can_retry(self):
        (self.dest / "python").mkdir(parents=True)
        marker = self.dest / "python/previous"
        marker.write_bytes(b"keep until replacement succeeds")
        self.assertEqual(self.install(fail=True), (False, 1))
        self.assertEqual(marker.read_bytes(), b"keep until replacement succeeds")
        self.assertFalse((self.dest / "installation.json").exists())
        self.assertEqual(self.install(), (True, 1))
