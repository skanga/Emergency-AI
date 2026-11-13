"""Unified startup distinguishes saved choices from incomplete installations."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import prepare


class StartupTests(unittest.TestCase):
    def setUp(self):
        from app import startup
        self.startup = startup
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.output = io.StringIO()
        stack.enter_context(contextlib.redirect_stdout(self.output))
        for module in (startup, prepare):
            for attr, dirname in (("RUNTIME_DIR", "runtime"), ("MODELS_DIR", "models"), ("ZIM_DIR", "zim")):
                (self.root / dirname).mkdir(exist_ok=True)
                stack.enter_context(patch.object(module, attr, str(self.root / dirname)))
        self.external = stack.enter_context(patch.object(startup, "detect_llm", return_value=None))
        stack.enter_context(patch.object(startup.KiwixClient, "available", return_value=False))
        self.llama = stack.enter_context(patch.object(startup, "find_llama_server", return_value=(None, None)))
        self.kiwix = stack.enter_context(patch.object(startup, "find_kiwix_serve", return_value=None))
        stack.enter_context(patch.object(startup, "find_model", return_value=None))
        stack.enter_context(patch.object(startup, "platform_key", return_value="linux-x86_64"))
        self.settings = {"llm_backend": "auto"}

    def save(self, **kwargs):
        selection = dict(model="none", zims="none", archives="none", python=False)
        selection.update(kwargs)
        self.startup.save_selection(selection)

    def test_first_run_and_remembered_guide_only_choice(self):
        self.assertEqual(self.startup.inspect(self.settings)["state"], "first_run")
        with patch("builtins.input", return_value="2"), patch.object(prepare, "run") as download:
            self.startup.ensure_ready(self.settings, interactive=True)
            self.startup.ensure_ready(self.settings, interactive=True)
        download.assert_not_called()
        self.assertEqual(self.startup.inspect(self.settings)["state"], "ready")

    def test_noninteractive_start_does_not_prompt_download_or_save_choice(self):
        with patch("builtins.input") as ask, patch.object(prepare, "run") as download:
            self.startup.ensure_ready(self.settings, interactive=False)
        ask.assert_not_called()
        download.assert_not_called()
        self.assertFalse((self.root / "runtime" / "setup.json").exists())

    def test_running_external_model_does_not_trigger_first_run(self):
        self.external.return_value = object()
        report = self.startup.inspect(self.settings)
        self.assertEqual(report["state"], "available")
        self.assertTrue(report["external_llm"])

    def test_ready_selection_uses_selected_model_without_preparation(self):
        self.save(model="strong")
        cfg = {"models": [{"id": "strong", "file": "strong.gguf", "size_bytes": 3}]}
        (self.root / "models" / "strong.gguf").write_bytes(b"abc")
        self.llama.return_value = ("llama-server", "llama.cpp")
        actual_load = self.startup.load_json
        def load(path, default=None):
            return cfg if path.endswith("models.json") else actual_load(path, default)
        with patch.object(self.startup, "load_json", side_effect=load), patch("builtins.input") as ask, \
                patch.object(prepare, "run") as setup:
            report = self.startup.ensure_ready(self.settings, interactive=True)
        self.assertEqual(report["state"], "ready")
        self.assertEqual(self.settings.get("model_file"), "strong.gguf")
        ask.assert_not_called()
        setup.assert_not_called()

    def test_external_kiwix_does_not_hide_missing_selected_libraries(self):
        self.save(zims="minimal")
        with patch.object(self.startup.KiwixClient, "available", return_value=True), \
                patch.object(self.startup.KiwixClient, "books", return_value=[]):
            report = self.startup.inspect(self.settings)
        self.assertEqual(report["state"], "incomplete")
        self.assertFalse(any("Kiwix server" in m for m in report["missing"]))

    def test_saved_gui_model_takes_priority_over_old_download_selection(self):
        self.save(model="gemma4-e2b")
        self.settings['model_file'] = 'custom.gguf'
        (self.root / 'models' / 'custom.gguf').write_bytes(b'GGUF')
        self.llama.return_value = ('llama-server', 'llama.cpp')
        with patch('builtins.input', return_value='2') as ask, patch.object(prepare, 'run') as setup:
            report = self.startup.ensure_ready(self.settings, interactive=True)
        self.assertEqual(report['state'], 'ready')
        self.assertEqual(self.settings['model_file'], 'custom.gguf')
        ask.assert_not_called()
        setup.assert_not_called()

    def test_model_selection_checks_file_size_and_current_platform_engine(self):
        self.save(model="gemma4-e2b")
        model = next(m for m in prepare.load_json(str(Path(prepare.CONFIG_DIR) / "models.json"))["models"] if m["id"] == "gemma4-e2b")
        path = self.root / "models" / model["file"]
        path.write_bytes(b"truncated")
        report = self.startup.inspect(self.settings)
        self.assertEqual(report["state"], "incomplete")
        self.assertTrue(any("model" in m.lower() for m in report["missing"]))
        self.assertTrue(any("linux-x86_64" in m for m in report["missing"]))
        # A ready manifest from another machine must not bypass actual files.
        (self.root / "runtime" / "kit-info.json").write_text('{"ready": true}')
        self.assertEqual(self.startup.inspect(self.settings)["state"], "incomplete")

    def test_partial_library_profile_is_not_ready(self):
        self.save(zims="minimal")
        self.kiwix.return_value = "kiwix-serve"
        (self.root / "zim" / "wikipedia_en_medicine_maxi_2026-01.zim").write_bytes(b"library")
        report = self.startup.inspect(self.settings)
        self.assertEqual(report["state"], "incomplete")
        self.assertTrue(any("zimgit-water_en" in m for m in report["missing"]))

    def test_archive_partial_file_does_not_count_as_installed(self):
        self.save(archives="wikem")
        self.kiwix.return_value = "kiwix-serve"
        (self.root / "zim" / "wikem_en_all_maxi_2020-06.zim.part").write_bytes(b"partial")
        self.assertIn("Archive: wikem (2020-06)", self.startup.inspect(self.settings)["missing"])

    def test_interrupted_preparation_saves_choices_before_download(self):
        def interrupted(*args):
            selection = json.loads((self.root / "runtime" / "setup.json").read_text())
            self.assertEqual(selection["archives"], "wikem")
            raise KeyboardInterrupt
        with patch.object(prepare, "get_archive", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                prepare.run(model="none", zims="none", archives="wikem", oses="this",
                            python=False, yes=True, skip_tools=True)

    def test_resume_keeps_choices_and_targets_current_platform(self):
        self.save(archives="wikem")
        with patch("builtins.input", return_value="1"), patch.object(prepare, "run", return_value=1) as run:
            self.startup.ensure_ready(self.settings, interactive=True)
        self.assertTrue(run.call_args.kwargs["resume"])
        self.assertEqual(run.call_args.kwargs["oses"], "this")
        self.assertIn("available", self.output.getvalue().lower())

    def test_offline_repair_failure_does_not_block_available_guides(self):
        self.save(model="gemma4-e2b")
        with patch("builtins.input", return_value="1"), patch.object(prepare, "run", side_effect=OSError("offline")):
            report = self.startup.ensure_ready(self.settings, interactive=True)
        self.assertEqual(report["state"], "incomplete")

    def test_resume_downloads_only_saved_archive_selection(self):
        self.save(archives="wikem")
        with patch.object(prepare, "get_archive", return_value=True) as archive, \
                patch.object(prepare, "get_model") as model, patch.object(prepare, "get_zim") as zim:
            self.assertEqual(prepare.run(resume=True, yes=True, oses="this", skip_tools=True), 0)
        self.assertEqual(archive.call_args.args[0]["id"], "wikem")
        model.assert_not_called()
        zim.assert_not_called()

    def test_old_manifest_is_not_used_as_setup(self):
        (self.root / "runtime" / "kit-info.json").write_text(
            '{"model": null, "zim_profile": "none", "archives": [], "ready": true}')
        self.assertIsNone(self.startup.load_selection(str(self.root / "runtime")))

    def test_invalid_saved_selection_is_reported_without_crashing(self):
        self.save(model="removed-model")
        self.assertEqual(self.startup.inspect(self.settings)["state"], "incomplete")
