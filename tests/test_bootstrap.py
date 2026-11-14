"""Exercise bootstrap installers offline using tiny source/runtime archives."""

import contextlib
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from app import prepare

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="Emergency bootstrap ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, PYTHONHOME=sys.base_prefix)
        files = {"emergency.py": b"# fixture\n",
                 "run.bat": b'@echo off\r\necho %* > "%~dp0setup-args.txt"\r\nexit /b 0\r\n',
                 "run.sh": b'#!/bin/sh\nprintf "%s\\n" "$@" > "$(dirname "$0")/setup-args.txt"\n',
                 "run.command": b"#!/bin/sh\n",
                 "install.bat": b"rem source archive installer\r\n",
                 "install.sh": b"# source archive installer\n"}
        with zipfile.ZipFile(self.root / "source.zip", "w") as archive:
            for name, data in files.items():
                archive.writestr("Emergency-AI-main/" + name, data)
        with tarfile.open(self.root / "source.tar.gz", "w:gz") as archive:
            for name, data in files.items():
                info = tarfile.TarInfo("Emergency-AI-main/" + name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        self.runtime = self.root / "python.tar.gz"
        with tarfile.open(self.runtime, "w:gz") as archive:
            if os.name == "nt":
                archive.add(sys.executable, arcname="python/python.exe")
            else:
                data = b'#!/bin/sh\nexit 0\n'
                info = tarfile.TarInfo("python/bin/python3")
                info.mode = 0o755
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        self.env["BOOTSTRAP_FIXTURES"] = str(self.root)

    def run_installer(self, *, corrupt=False, fail=False, cwd=None, destination="installed kit", reply=None):
        cwd = cwd or self.root
        digest = hashlib.sha256(self.runtime.read_bytes()).hexdigest()
        # Substitute only the pinned digest; production download hosts stay fixed.
        name = "install.bat" if os.name == "nt" else "install.sh"
        script = (ROOT / name).read_text(encoding="utf-8")
        script = re.sub(r"\b[0-9a-f]{64}\b", "0" * 64 if corrupt else digest, script)
        if os.name == "nt":
            self.assertIn("\n# POWERSHELL\n", script, "Windows installer must contain its own implementation")
            mock_download = '''
function curl.exe {
    $Uri = $args[-1]
    $OutFile = $args[[Array]::IndexOf($args, '-o') + 1]
    Add-Content -LiteralPath (Join-Path $env:BOOTSTRAP_FIXTURES 'requests.txt') -Value ($args -join ' ')
    if ($env:BOOTSTRAP_FAIL -eq '1') { $global:LASTEXITCODE = 22; return }
    if ($Uri -like '*cpython*' -and $env:BOOTSTRAP_INTERRUPT -eq '1') {
        [IO.File]::WriteAllBytes($OutFile, [byte[]](1, 2, 3))
        $global:LASTEXITCODE = 18; return
    }
    if ($Uri -like '*cpython*' -and $env:BOOTSTRAP_NO_PYTHON -eq '1') {
        $global:LASTEXITCODE = 22; return
    }
    $name = if ($Uri -like '*cpython*') { 'python.tar.gz' } else { 'source.zip' }
    Copy-Item -LiteralPath (Join-Path $env:BOOTSTRAP_FIXTURES $name) -Destination $OutFile
    $global:LASTEXITCODE = 0
}
'''
            # Mock downloads inside the child PowerShell process; execute the real
            # batch entry point, including its argument and exit-code handling.
            parameter = "param([string]$Destination = 'Emergency-AI')"
            script = script.replace(parameter, parameter + "\n" + mock_download)
            if reply is not None:
                script = script.replace('[Console]::IsInputRedirected', '$false')
                script = script.replace(parameter, parameter + "\nfunction Read-Host { if ($args[0] -like 'Open Emergency*') { return 'n' }; return $env:BOOTSTRAP_REPLY }\n")
            command = ["cmd", "/d", "/c", name]
        else:
            if reply is not None:
                script = script.replace('[ -t 0 ]', 'true')
            mock = self.root / "bin"
            mock.mkdir(exist_ok=True)
            curl = mock / "curl"
            curl.write_text('''#!/bin/sh
echo "$*" >> "$BOOTSTRAP_FIXTURES/requests.txt"
[ "$BOOTSTRAP_FAIL" != 1 ] || exit 22
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) out=$2; shift 2 ;;
        *cpython*) source=python.tar.gz; shift ;;
        https:*) source=source.tar.gz; shift ;;
        *) shift ;;
    esac
done
if [ "$source" = python.tar.gz ] && [ "$BOOTSTRAP_INTERRUPT" = 1 ]; then
    printf abc > "$out"; exit 18
fi
if [ "$source" = python.tar.gz ] && [ "$BOOTSTRAP_NO_PYTHON" = 1 ]; then exit 22; fi
cp "$BOOTSTRAP_FIXTURES/$source" "$out"
''')
            curl.chmod(0o755)
            self.env["PATH"] = str(mock) + os.pathsep + os.environ["PATH"]
            command = ["sh", str(cwd / name)]
        if destination is not None:
            command.append(str(cwd / destination))
        (cwd / name).write_text(script, encoding="utf-8")
        self.env["BOOTSTRAP_FAIL"] = "1" if fail else "0"
        self.env["BOOTSTRAP_REPLY"] = reply or ""
        return subprocess.run(command, env=self.env, cwd=cwd, text=True,
                              input=(reply + "\n") if reply is not None else "",
                              capture_output=True, timeout=30)

    def test_download_extract_and_place_portable_runtime(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = self.root / "installed kit"
        self.assertTrue((target / "emergency.py").is_file())
        self.assertTrue(list((target / "runtime/python").glob("*/python/*")))
        self.assertFalse(list(self.root.glob(".emergency-install-*")))
        if os.name != "nt":
            self.assertTrue(os.access(target / "run.sh", os.X_OK))

    def test_existing_destination_is_never_overwritten(self):
        target = self.root / "installed kit"
        target.mkdir()
        marker = target / "personal.txt"
        marker.write_text("keep me")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "keep me")
        self.assertEqual(list(target.iterdir()), [marker])

    def test_bad_checksum_does_not_publish_installation(self):
        result = self.run_installer(corrupt=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum", (result.stdout + result.stderr).lower())
        self.assertFalse((self.root / "installed kit").exists())
        self.assertFalse(list(self.root.glob(".emergency-install-*")))

    def test_network_failure_can_be_retried(self):
        result = self.run_installer(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "installed kit").exists())
        self.assertEqual(self.run_installer().returncode, 0)

    def test_failed_download_leaves_readable_log(self):
        result = self.run_installer(fail=True)
        self.assertNotEqual(result.returncode, 0)
        logs = list(self.root.glob('.*-downloads/install.log'))
        self.assertEqual(len(logs), 1)
        self.assertIn('attempt', logs[0].read_text().lower())
        self.assertIn('install.log', result.stdout + result.stderr)

    def test_partial_python_download_survives_and_retry_requests_resume(self):
        self.env['BOOTSTRAP_INTERRUPT'] = '1'
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        partial = list(self.root.glob('.*-downloads/cpython*.part'))
        self.assertEqual(len(partial), 1)
        self.assertEqual(partial[0].stat().st_size, 3)
        self.env['BOOTSTRAP_INTERRUPT'] = '0'
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('-C -', (self.root / 'requests.txt').read_text())

    def test_verified_python_cache_is_reused_after_retry(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = self.root / 'installed kit'
        self.assertEqual(target.parent, self.root)
        shutil.rmtree(target)
        self.env['BOOTSTRAP_NO_PYTHON'] = '1'
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Reusing verified', result.stdout)

    def test_default_uses_current_emergency_ai_folder_with_downloaded_installer(self):
        target = self.root / "Emergency-AI"
        target.mkdir()
        result = self.run_installer(cwd=target, destination=None)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((target / "emergency.py").is_file())
        self.assertFalse((target / "Emergency-AI").exists())
        installer = target / ("install.bat" if os.name == "nt" else "install.sh")
        self.assertIn("Installation failed:", installer.read_text())

    def test_default_creates_subfolder_from_other_folder(self):
        result = self.run_installer(destination=None)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "Emergency-AI/emergency.py").is_file())

    def test_explicit_empty_destination_is_used(self):
        target = self.root / "installed kit"
        target.mkdir()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((target / "emergency.py").is_file())

    def test_current_emergency_ai_folder_with_existing_files_is_refused(self):
        target = self.root / "Emergency-AI"
        target.mkdir()
        marker = target / "personal.txt"
        marker.write_text("keep me")
        result = self.run_installer(cwd=target, destination=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "keep me")
        self.assertFalse((target / "Emergency-AI").exists())

    def test_accepting_offer_runs_launcher_with_prepare(self):
        result = self.run_installer(reply="y")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "installed kit/setup-args.txt").read_text().strip(), "prepare")

    def test_declining_offer_does_not_start_setup(self):
        result = self.run_installer(reply="n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "installed kit/setup-args.txt").exists())

    def test_noninteractive_install_does_not_start_setup(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "installed kit/setup-args.txt").exists())

    def test_preparation_reuses_bootstrapped_python_without_download(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        runtime = self.root / "installed kit/runtime"
        platform = next((runtime / "python").iterdir()).name
        with patch.object(prepare, "RUNTIME_DIR", str(runtime)), \
                patch.object(prepare, "github_latest_assets") as metadata, \
                patch.object(prepare, "download") as download, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(prepare.get_python(platform, prepare.T["en"]))
        metadata.assert_not_called()
        download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
