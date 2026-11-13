"""Installation failure, integrity and command status regressions."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import prepare


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.enter.enter_context(patch.object(prepare, "RUNTIME_DIR", str(self.root / "runtime")))
        self.enter.enter_context(patch.object(prepare, "MODELS_DIR", str(self.root / "models")))
        self.enter.enter_context(patch.object(prepare, "ZIM_DIR", str(self.root / "zim")))
        for name in ("runtime", "models", "zim"):
            (self.root / name).mkdir()
        self.enter.enter_context(patch.object(prepare.shutil, "which", return_value=None))
        self.enter.enter_context(patch.object(prepare.time, "sleep"))

    def fake_response(self, data, headers, status=200):
        response = io.BytesIO(data)
        response.headers = headers
        response.status = status
        return patch.object(prepare.urllib.request, "urlopen", return_value=response)

    def test_short_response_never_becomes_completed_download(self):
        dest = str(self.root / "download.bin")
        with self.fake_response(b"abc", {"Content-Length": "100"}):
            with self.assertRaises(RuntimeError):
                prepare.download("https://example.invalid/file", dest, retries=1)
        self.assertFalse(Path(dest).exists())
        self.assertEqual(Path(dest + ".part").read_bytes(), b"abc")

    def test_expected_size_verified_even_without_content_length(self):
        dest = str(self.root / "download.bin")
        with self.fake_response(b"abc", {}):
            with self.assertRaises(RuntimeError):
                prepare.download("https://example.invalid/file", dest, expected_size=100, retries=1)
        self.assertFalse(Path(dest).exists())

    def test_resume_rejects_wrong_content_range(self):
        dest = str(self.root / "download.bin")
        Path(dest + ".part").write_bytes(b"abc")
        with self.fake_response(b"xyz", {"Content-Length": "3", "Content-Range": "bytes 0-2/6"}, 206):
            with self.assertRaises(RuntimeError):
                prepare.download("https://example.invalid/file", dest, retries=1)
        self.assertEqual(Path(dest + ".part").read_bytes(), b"abc")

    def test_valid_resume_activates_complete_file(self):
        dest = str(self.root / "download.bin")
        Path(dest + ".part").write_bytes(b"abc")
        with self.fake_response(b"def", {"Content-Length": "3", "Content-Range": "bytes 3-5/6"}, 206):
            prepare.download("https://example.invalid/file", dest, expected_size=6, retries=1)
        self.assertEqual(Path(dest).read_bytes(), b"abcdef")

    def test_existing_corrupt_file_does_not_bypass_checksum(self):
        dest = str(self.root / "download.bin")
        Path(dest).write_bytes(b"bad")
        with self.fake_response(b"new", {"Content-Length": "3"}):
            prepare.download("https://example.invalid/file", dest,
                             sha256=hashlib.sha256(b"new").hexdigest(), retries=1)
        self.assertEqual(Path(dest).read_bytes(), b"new")

    def test_failed_zim_update_keeps_previous_library(self):
        old = self.root / "zim" / "example_2025-01.zim"
        old.write_bytes(b"working library")
        item = {"url": "https://example.invalid/example_2026-01.zim", "title": "Example", "size": 50}
        with patch.object(prepare, "catalog_lookup", return_value=[item]), \
                patch.object(prepare, "download", side_effect=OSError("connection lost")):
            self.assertFalse(prepare.get_zim({"name": "example"}, "catalog", prepare.T["en"]))
        self.assertEqual(old.read_bytes(), b"working library")

    def test_successful_zim_update_retires_old_after_download(self):
        old = self.root / "zim" / "example_2025-01.zim"
        old.write_bytes(b"old")
        item = {"url": "https://example.invalid/example_2026-01.zim", "title": "Example", "size": 3}

        def fetch(url, dest, **kwargs):
            self.assertTrue(old.exists())
            self.assertEqual(kwargs["expected_size"], 3)
            Path(dest).write_bytes(b"new")

        with patch.object(prepare, "catalog_lookup", return_value=[item]), patch.object(prepare, "download", side_effect=fetch):
            self.assertTrue(prepare.get_zim({"name": "example"}, "catalog", prepare.T["en"]))
        self.assertFalse(old.exists())

    def test_zim_uses_exact_metalink_size_and_requested_variant(self):
        entries = [{"url": "https://example.invalid/example_maxi_2026-01.zim", "title": "Example"},
                   {"url": "https://example.invalid/example_nopic_2026-01.zim", "title": "Example", "size": 1024,
                    "meta4": "https://example.invalid/file.meta4"}]
        xml = '<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="x"><size>3</size><hash type="sha-256">' + hashlib.sha256(b"new").hexdigest() + '</hash></file></metalink>'

        def fetch(url, dest, **kwargs):
            self.assertIn("_nopic_", url)
            self.assertEqual(kwargs["expected_size"], 3)
            self.assertEqual(kwargs["sha256"], hashlib.sha256(b"new").hexdigest())
            Path(dest).write_bytes(b"new")

        with patch.object(prepare, "catalog_lookup", return_value=entries), patch.object(prepare, "get_text", return_value=xml), \
                patch.object(prepare, "download", side_effect=fetch):
            self.assertTrue(prepare.get_zim({"name": "example", "variant": "nopic"}, "catalog", prepare.T["en"]))

    def test_invalid_selections_fail_before_downloads(self):
        for overrides in ({"model": "standrad"}, {"zims": "minmal"}, {"oses": "windows-typo"}):
            args = dict(model="none", zims="none", oses="this", python=False, yes=True, skip_tools=True)
            args.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                prepare.run(**args)

    def test_failed_preparation_keeps_partial_download_and_records_failure(self):
        partial = self.root / "runtime" / "_downloads" / "engine.zip.part"
        partial.parent.mkdir()
        partial.write_bytes(b"partial download")
        with patch.object(prepare, "get_llama", return_value=False), patch.object(prepare, "get_model", return_value=True):
            status = prepare.run(model="standard", zims="none", oses="this", python=False, yes=True)
        self.assertEqual(status, 1)
        self.assertTrue(partial.exists())
        manifest = json.loads((self.root / "runtime" / "kit-info.json").read_text())
        self.assertFalse(manifest["ready"])
        self.assertTrue(any(not c["ok"] for c in manifest["components"]))

    def test_explicit_search_only_preparation_succeeds(self):
        self.assertEqual(prepare.run(model="none", zims="none", oses="this", python=False, yes=True), 0)

    def test_setup_preferences_survive_interruption_before_manifest(self):
        with patch.object(prepare, "get_model", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                prepare.run(model="standard", zims="none", oses="this", python=False,
                            yes=True, skip_tools=True)
        saved = self.root / "runtime" / "setup.json"
        self.assertTrue(saved.exists(), "Save choices before starting downloads")
        self.assertEqual(json.loads(saved.read_text())["model"], "standard")
