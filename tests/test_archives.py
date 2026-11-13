"""Archived libraries are opt-in, verified before activation, and dated in citations."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import prepare
from app.engine import Engine
from app.kiwix import KiwixClient


def zim_bytes():
    # Minimal checksum fixture, not an article database.
    header = bytearray(80)
    header[:6] = b"ZIM\x04\x06\x00"
    header[56:64] = (80).to_bytes(8, "little")
    payload = b"archived reference text"
    header[72:80] = (80 + len(payload)).to_bytes(8, "little")
    data = bytes(header) + payload
    return data + hashlib.md5(data).digest()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.output = io.StringIO()
        stack.enter_context(contextlib.redirect_stdout(self.output))
        for attr, dirname in (("RUNTIME_DIR", "runtime"), ("MODELS_DIR", "models"), ("ZIM_DIR", "zim")):
            (self.root / dirname).mkdir()
            stack.enter_context(patch.object(prepare, attr, str(self.root / dirname)))
        stack.enter_context(patch.object(prepare.shutil, "which", return_value=None))
        stack.enter_context(patch.object(prepare.time, "sleep"))

    def run_kit(self, **overrides):
        args = dict(model="none", zims="none", oses="this", python=False, yes=True)
        args.update(overrides)
        return prepare.run(**args)

    def manifest(self):
        return json.loads((self.root / "runtime" / "kit-info.json").read_text(encoding="utf-8"))

    def test_all_profiles_leave_archives_out_by_default(self):
        with patch.object(prepare, "download") as fetch, \
                patch.object(prepare, "get_zim", return_value=True), \
                patch.object(prepare, "get_kiwix_tools", return_value=True):
            for profile in ("minimal", "recommended", "full", "none"):
                self.assertEqual(self.run_kit(zims=profile), 0)
                self.assertEqual(self.manifest().get("archives"), [])
            fetch.assert_not_called()

    def test_explicit_archives_download_once_and_record_dates(self):
        def fetch(url, dest, **kwargs):
            self.assertEqual(kwargs["expected_size"], 62896704)
            self.assertTrue(kwargs["verify_zim"])
            Path(dest).write_bytes(zim_bytes())

        newer = self.root / "zim" / "wikem_en_all_maxi_2025-01.zim"
        newer.write_bytes(b"keep manually installed newer edition")
        with patch.object(prepare, "download", side_effect=fetch) as download, \
                patch.object(prepare, "catalog_lookup") as catalog, \
                patch.object(prepare, "get_kiwix_tools", return_value=True) as tools:
            self.assertEqual(self.run_kit(archives="wikem,wikem"), 0)
        download.assert_called_once()
        catalog.assert_not_called()
        tools.assert_called_once()
        self.assertTrue(newer.exists())
        self.assertIn("ARCHIVED 2020-06", self.output.getvalue())
        self.assertIn("outdated", self.output.getvalue())
        self.assertEqual(self.manifest()["archives"][0]["snapshot"], "2020-06")

    def test_unknown_archive_rejected_before_any_download(self):
        with patch.object(prepare, "download") as fetch:
            with self.assertRaises(ValueError):
                self.run_kit(archives="wikem,typo")
            fetch.assert_not_called()

    def test_wizard_defaults_to_no_archives_and_shows_dates_and_sizes(self):
        with patch("builtins.input", side_effect=["none", "none", "", "this", "n", "y"]), \
                patch.object(prepare, "download") as fetch:
            self.assertEqual(prepare.run(), 0)
        self.assertEqual(self.manifest()["archives"], [])
        self.assertIn("ARCHIVED 2020-06", self.output.getvalue())
        self.assertIn("83.5 GiB", self.output.getvalue())
        fetch.assert_not_called()

    def test_failed_archive_marks_kit_not_ready(self):
        with patch.object(prepare, "download", side_effect=OSError("offline")):
            self.assertEqual(self.run_kit(archives="wikem", skip_tools=True), 1)
        self.assertFalse(self.manifest()["ready"])

    def test_all_archive_option_selects_four_fixed_snapshots(self):
        with patch.object(prepare, "download", side_effect=lambda url, dest, **kw: Path(dest).write_bytes(zim_bytes())) as fetch:
            self.assertEqual(self.run_kit(archives="all", skip_tools=True), 0)
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual({a["id"] for a in self.manifest()["archives"]},
                         {"wikem", "wikihow-en", "wikihow-es", "wikihow-pt"})

    def test_archive_download_rejects_corruption_before_activation(self):
        valid = zim_bytes()
        bad = bytearray(valid)
        bad[85] ^= 1
        for data in (bytes(bad), b"x" * len(valid)):
            dest = self.root / "zim" / "archive.zim"
            dest.write_bytes(b"working older edition")
            response = io.BytesIO(data)
            response.headers = {"Content-Length": str(len(data))}
            response.status = 200
            with patch.object(prepare.urllib.request, "urlopen", return_value=response):
                with self.assertRaises(RuntimeError):
                    prepare.download("https://example.invalid/archive.zim", str(dest),
                                     expected_size=len(data), verify_zim=True, retries=1)
            self.assertEqual(dest.read_bytes(), b"working older edition")

    def test_same_size_corruption_is_repaired_and_valid_download_is_reused(self):
        valid = zim_bytes()
        dest = self.root / "zim" / "archive.zim"
        bad = bytearray(valid)
        bad[85] ^= 1
        dest.write_bytes(bad)
        response = io.BytesIO(valid)
        response.headers = {"Content-Length": str(len(valid))}
        response.status = 200
        with patch.object(prepare.urllib.request, "urlopen", return_value=response) as fetch:
            for _ in range(2):
                prepare.download("https://example.invalid/archive.zim", str(dest),
                                 expected_size=len(valid), verify_zim=True, retries=1)
        fetch.assert_called_once()
        self.assertEqual(dest.read_bytes(), valid)

    def test_corrupt_new_download_is_not_installed(self):
        data = bytearray(zim_bytes())
        data[85] ^= 1
        dest = self.root / "zim" / "archive.zim"
        response = io.BytesIO(data)
        response.headers = {"Content-Length": str(len(data))}
        response.status = 200
        with patch.object(prepare.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "ZIM"):
                prepare.download("https://example.invalid/archive.zim", str(dest),
                                 expected_size=len(data), verify_zim=True, retries=1)
        self.assertFalse(dest.exists())
        self.assertFalse(Path(str(dest) + ".part").exists())


class ArchiveCitationTests(unittest.TestCase):
    def test_catalog_issue_date_survives_into_answer_and_model_context(self):
        # Kiwix can expose an unversioned name and a separate publication date.
        xml = '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/terms/"><entry><name>wikem_en_all</name><title>WikEM</title><language>eng</language><dc:issued>2020-06-15T00:00:00Z</dc:issued><updated>2026-11-12T00:00:00Z</updated></entry></feed>'
        results = '<rss><item><title>Example</title><link>/content/book/Example</link></item></rss>'
        engine = Engine({"llm_backend": "none"})
        with patch.object(engine.kb, "search", return_value=[]), \
                patch.object(engine, "kiwix_ok", return_value=True), \
                patch("app.kiwix.get_text", side_effect=[xml, results, "<p>Example reference text.</p>"]):
            sources = engine.retrieve("example", "en")
        label = "ARCHIVED 2020-06"
        self.assertIn(label, sources[0]["doc_title"])
        self.assertIn(label, engine.extractive_answer("en", sources))
        self.assertIn(label, engine.build_messages("example", "en", sources)[-1]["content"])

    def test_book_dates_reach_search_citations_without_inventing_dates(self):
        for name, expected in (("wikem_en_all_maxi_2020-06", "ARCHIVED 2020-06"),
                               ("wikihow_en_maxi_2023-03", "ARCHIVED 2023-03"),
                               ("wikem_en_all", "ARCHIVED; snapshot date unknown"),
                               ("wikipedia_en_medicine_maxi_2026-01", None)):
            with self.subTest(name=name):
                xml = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><name>' + name + '</name><title>Reference</title><language>eng</language><updated>2026-11-12T00:00:00Z</updated></entry></feed>'
                results = '<rss><item><title>Page</title><link>/content/book/Page</link></item></rss>'
                client = KiwixClient("http://localhost:8092")
                with patch("app.kiwix.get_text", side_effect=[xml, results]):
                    title = client.search("page")[0]["book"]
                if expected:
                    self.assertIn(expected, title)
                    self.assertIn("outdated", title)
                else:
                    self.assertEqual(title, "Reference")
