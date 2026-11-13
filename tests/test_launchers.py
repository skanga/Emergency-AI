"""Run the actual launch scripts from a folder containing spaces."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows architecture dispatch")
    def test_arm_windows_prefers_arm_portable_python_in_universal_kit(self):
        with tempfile.TemporaryDirectory(prefix="Survival kit ") as folder:
            root = Path(folder)
            shutil.copy2(ROOT / "run.bat", root / "run.bat")
            (root / "survival.py").write_text("print('native interpreter selected')\n")
            arm = root / "runtime/python/windows-arm64/python"
            x64 = root / "runtime/python/windows-x86_64/python"
            arm.mkdir(parents=True)
            x64.mkdir(parents=True)
            # Test path selection with the test interpreter, not ARM execution.
            shutil.copy2(sys.executable, arm / "python.exe")
            (x64 / "python.exe").write_bytes(b"wrong interpreter")
            env = dict(os.environ, PYTHONHOME=sys.base_prefix, PROCESSOR_ARCHITECTURE="AMD64",
                       PROCESSOR_ARCHITEW6432="ARM64")
            result = subprocess.run(["cmd", "/c", "run.bat"], cwd=root, env=env, input="\n",
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("native interpreter selected", result.stdout)

    def test_launcher_preserves_interpreter_path_arguments_and_exit_status(self):
        with tempfile.TemporaryDirectory(prefix="Survival kit ") as folder:
            root = Path(folder)
            probe = "import json,sys; print(json.dumps(sys.argv[1:])); sys.exit(7)\n"
            (root / "survival.py").write_text(probe, encoding="utf-8")
            if os.name == "nt":
                portable = root / "runtime/python/windows-x86_64/python"
                portable.mkdir(parents=True)
                # Exercise the real executable at a spaced path, with its stdlib
                # supplied by the test interpreter's installation.
                exe = portable / "python.exe"
                shutil.copy2(sys.executable, exe)
                env = dict(os.environ, PYTHONHOME=sys.base_prefix)
                # A universal kit may contain both architectures. The other
                # executable must not override the native interpreter.
                other = root / "runtime/python/windows-arm64/python"
                other.mkdir(parents=True)
                (other / "python.exe").write_bytes(b"not an x64 executable")
                env["PROCESSOR_ARCHITECTURE"] = "AMD64"
                env.pop("PROCESSOR_ARCHITEW6432", None)
                scripts = ("run.bat",)
            else:
                env = os.environ.copy()
                scripts = ("run.sh",)
            for name in scripts:
                shutil.copy2(ROOT / name, root / name)
            for name in scripts:
                with self.subTest(script=name):
                    if os.name == "nt":
                        cmd = ["cmd", "/c", name, "--lang", "en"]
                    else:
                        cmd = ["sh", name, "--lang", "en"]
                    result = subprocess.run(cmd, cwd=root, env=env, input="\n", text=True,
                                            capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
                    self.assertIn('"--lang", "en"', result.stdout)

    def test_prepare_cli_rejects_unknown_selection(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "survival.py"), "prepare", "--yes",
                                 "--model", "typo", "--zims", "none", "--skip-tools"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown model", result.stderr)
