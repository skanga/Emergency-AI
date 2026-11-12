"""Release-selection regressions for the offline kit preparer."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import prepare


class LlamaReleaseTests(unittest.TestCase):
    def run_preparer(self, releases, existing=False, installed=None, extract_error=False,
                     short_download=False, activation_error=False):
        def metadata(url, **kwargs):
            if url.endswith("/releases/latest"):
                return releases[0]
            self.assertEqual(url, "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10")
            return releases

        def download(url, dest, **kwargs):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"x" * (3 if short_download else 123))
            return dest

        def unpack(archive, dest):
            if extract_error:
                raise OSError("incomplete archive")
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "llama-server.exe").write_bytes(b"new engine")

        replace = os.replace

        def activate(source, destination):
            if activation_error and Path(source).name == "new":
                raise OSError("simulated activation failure")
            return replace(source, destination)

        with tempfile.TemporaryDirectory() as runtime:
            dest = Path(runtime) / "llama.cpp" / "windows-x86_64"
            if existing:
                dest.mkdir(parents=True)
                (dest / "llama-server.exe").write_bytes(b"old engine")
                (dest / "obsolete.dll").write_bytes(b"old dependency")
            if installed:
                (dest / "release.json").write_text(json.dumps(installed), encoding="utf-8")
            with patch.object(prepare, "RUNTIME_DIR", runtime), \
                    patch.object(prepare, "get_json", side_effect=metadata) as get_metadata, \
                    patch.object(prepare, "download", side_effect=download) as fetch, \
                    patch.object(prepare, "extract", side_effect=unpack) as extract, \
                    patch.object(prepare.os, "replace", side_effect=activate), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = prepare.get_llama("windows-x86_64", prepare.T["en"])
                self.metadata_calls = get_metadata.call_count
                self.installed_files = {p.name: p.read_bytes() for p in dest.glob("*") if p.is_file()}
                return result, fetch.call_args_list, extract.call_count

    def asset(self, name):
        return {"name": name, "browser_download_url": "https://example.invalid/" + name, "size": 123}

    def test_skips_release_without_binaries(self):
        name = "llama-b123-bin-win-cpu-x64.zip"
        result, calls, extracts = self.run_preparer([
            {"tag_name": "v0.9.0", "assets": []},
            {"tag_name": "b123", "assets": [self.asset(name)]},
        ])
        self.assertTrue(result)
        self.assertEqual(calls[0].args[0], "https://example.invalid/" + name)
        self.assertEqual(calls[0].kwargs["expected_size"], 123)
        self.assertEqual(extracts, 1)

    def test_skips_release_without_requested_platform(self):
        name = "llama-b122-bin-win-cpu-x64.zip"
        result, calls, _ = self.run_preparer([
            {"tag_name": "b123", "assets": [self.asset("llama-b123-bin-macos-arm64.tar.gz")]},
            {"tag_name": "b122", "assets": [self.asset(name)]},
        ])
        self.assertTrue(result)
        self.assertEqual(calls[0].args[0], "https://example.invalid/" + name)

    def test_no_matching_release_does_not_download(self):
        result, calls, extracts = self.run_preparer([{"tag_name": "v0.9.0", "assets": []}])
        self.assertFalse(result)
        self.assertEqual(calls, [])
        self.assertEqual(extracts, 0)

    def test_existing_unversioned_installation_is_updated(self):
        name = "llama-b124-bin-win-cpu-x64.zip"
        result, calls, _ = self.run_preparer([
            {"tag_name": "b124", "assets": [self.asset(name)]},
        ], existing=True)
        self.assertTrue(result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.installed_files["llama-server.exe"], b"new engine")
        self.assertNotIn("obsolete.dll", self.installed_files)
        self.assertEqual(json.loads(self.installed_files["release.json"])["tag"], "b124")

    def test_current_installation_checks_for_updates_without_redownloading(self):
        name = "llama-b124-bin-win-cpu-x64.zip"
        result, calls, _ = self.run_preparer([
            {"tag_name": "b124", "assets": [self.asset(name)]},
        ], existing=True, installed={"tag": "b124", "asset": name})
        self.assertTrue(result)
        self.assertEqual(self.metadata_calls, 1)
        self.assertEqual(calls, [])

    def test_failed_update_preserves_working_installation(self):
        name = "llama-b124-bin-win-cpu-x64.zip"
        result, calls, _ = self.run_preparer([
            {"tag_name": "b124", "assets": [self.asset(name)]},
        ], existing=True, extract_error=True)
        self.assertFalse(result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.installed_files["llama-server.exe"], b"old engine")
        self.assertIn("obsolete.dll", self.installed_files)

    def test_truncated_update_is_not_installed(self):
        name = "llama-b124-bin-win-cpu-x64.zip"
        result, _, extracts = self.run_preparer([
            {"tag_name": "b124", "assets": [self.asset(name)]},
        ], existing=True, short_download=True)
        self.assertFalse(result)
        self.assertEqual(extracts, 0)
        self.assertEqual(self.installed_files["llama-server.exe"], b"old engine")

    def test_newest_build_replaces_previous_version(self):
        name = "llama-b125-bin-win-cpu-x64.zip"
        result, calls, _ = self.run_preparer([
            {"tag_name": "b125", "assets": [self.asset(name)]},
            {"tag_name": "b124", "assets": [self.asset("llama-b124-bin-win-cpu-x64.zip")]},
        ], existing=True, installed={"tag": "b124", "asset": "llama-b124-bin-win-cpu-x64.zip"})
        self.assertTrue(result)
        self.assertEqual(calls[0].args[0], "https://example.invalid/" + name)
        self.assertEqual(json.loads(self.installed_files["release.json"])["tag"], "b125")

    def test_failed_activation_restores_previous_version(self):
        name = "llama-b125-bin-win-cpu-x64.zip"
        result, _, _ = self.run_preparer([
            {"tag_name": "b125", "assets": [self.asset(name)]},
        ], existing=True, activation_error=True)
        self.assertFalse(result)
        self.assertEqual(self.installed_files["llama-server.exe"], b"old engine")
        self.assertIn("obsolete.dll", self.installed_files)
