"""Regression checks for the English-first defaults and entry points."""

import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import tempfile
import contextlib
import io

from app import prepare
from app.engine import Engine
from app.knowledge import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]


class EnglishDefaultsTests(unittest.TestCase):
    def test_default_settings(self):
        settings = json.loads((ROOT / "config/settings.json").read_text())
        self.assertEqual(settings["language"], "en")

    def test_default_and_unknown_language_answers(self):
        engine = Engine({"llm_backend": "none", "kiwix_enabled": False})
        for kwargs in ({}, {"lang": "unknown"}):
            text, sources, _ = engine.answer_text("how to purify water", **kwargs)
            self.assertIn("Search-only mode", text)
            self.assertTrue(sources)
            self.assertTrue(all(s["lang"] == "en" for s in sources))

    def test_default_guide_search(self):
        results = KnowledgeBase().search("how to purify water")
        self.assertTrue(results)
        self.assertTrue(all(chunk.lang == "en" for _, chunk in results))

    def test_english_entry_points_and_help(self):
        for stem in ("start", "prepare-kit"):
            for suffix in (".bat", ".sh", ".command"):
                self.assertTrue((ROOT / (stem + suffix)).is_file())
        result = subprocess.run([sys.executable, str(ROOT / "survival.py"), "prepare", "--help"],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("minimal | recommended | full | none", result.stdout)

    def test_english_download_profiles(self):
        models = json.loads((ROOT / "config/models.json").read_text(encoding="utf-8"))
        self.assertEqual(models["default"], "standard")
        self.assertTrue({"light", "standard", "strong"} <= {m["id"] for m in models["models"]})
        zims = json.loads((ROOT / "config/zims.json").read_text(encoding="utf-8"))
        self.assertEqual(set(zims["profiles"]), {"minimal", "recommended", "full"})

    def test_preparer_selects_english_model_and_profile(self):
        with tempfile.TemporaryDirectory() as runtime, \
                patch.object(prepare, "RUNTIME_DIR", runtime), \
                patch.object(prepare, "get_model", return_value=True) as get_model, \
                patch.object(prepare, "get_zim", return_value=True) as get_zim, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            prepare.run(model="standard", zims="minimal", oses="this", python=False,
                        yes=True, skip_tools=True)
            self.assertEqual(get_model.call_args.args[0]["id"], "standard")
            self.assertGreater(get_zim.call_count, 0)
            self.assertTrue(all("minimal" in c.args[0]["profiles"] for c in get_zim.call_args_list))
            self.assertIn("Kit preparer — Survival AI", output.getvalue())
            self.assertIn("Kit ready!", output.getvalue())

    def test_preparer_none_skips_downloads(self):
        with tempfile.TemporaryDirectory() as runtime, \
                patch.object(prepare, "RUNTIME_DIR", runtime), \
                patch.object(prepare, "get_model") as get_model, \
                patch.object(prepare, "get_zim") as get_zim, \
                contextlib.redirect_stdout(io.StringIO()):
            prepare.run(model="none", zims="none", oses="this", python=False,
                        yes=True, skip_tools=True)
            get_model.assert_not_called()
            get_zim.assert_not_called()
