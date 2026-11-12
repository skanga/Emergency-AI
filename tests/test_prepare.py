"""Release-selection regressions for the offline kit preparer."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import prepare


class LlamaReleaseTests(unittest.TestCase):
    def run_preparer(self, releases):
        def metadata(url, **kwargs):
            if url.endswith("/releases/latest"):
                return releases[0]
            self.assertEqual(url, "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10")
            return releases

        def download(url, dest, **kwargs):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"test archive")
            return dest

        with tempfile.TemporaryDirectory() as runtime, \
                patch.object(prepare, "RUNTIME_DIR", runtime), \
                patch.object(prepare, "get_json", side_effect=metadata), \
                patch.object(prepare, "download", side_effect=download) as fetch, \
                patch.object(prepare, "extract") as extract, \
                contextlib.redirect_stdout(io.StringIO()):
            result = prepare.get_llama("windows-x86_64", prepare.T["en"])
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
