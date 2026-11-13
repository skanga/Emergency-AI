"""Exercise bootstrap installers offline using tiny source/runtime archives."""

import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="Emergency bootstrap ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, PYTHONHOME=sys.base_prefix)
        files = {"emergency.py": b"# fixture\n", "run.bat": b"@echo off\r\n",
                 "run.sh": b"#!/bin/sh\n", "run.command": b"#!/bin/sh\n"}
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

    def run_installer(self, *, corrupt=False, fail=False):
        digest = hashlib.sha256(self.runtime.read_bytes()).hexdigest()
        # Substitute only the pinned digest; production download hosts stay fixed.
        name = "install.bat" if os.name == "nt" else "install.sh"
        script = (ROOT / name).read_text(encoding="utf-8")
        script = re.sub(r"\b[0-9a-f]{64}\b", "0" * 64 if corrupt else digest, script)
        if os.name == "nt":
            self.assertIn("\n# POWERSHELL\n", script, "Windows installer must contain its own implementation")
            mock_download = '''
function Invoke-WebRequest {
    param($Uri, $OutFile, [switch]$UseBasicParsing)
    if ($env:BOOTSTRAP_FAIL -eq '1') { throw 'simulated connection failure' }
    $name = if ($Uri -like '*cpython*') { 'python.tar.gz' } else { 'source.zip' }
    Copy-Item -LiteralPath (Join-Path $env:BOOTSTRAP_FIXTURES $name) -Destination $OutFile
}
'''
            # Mock downloads inside the child PowerShell process; execute the real
            # batch entry point, including its argument and exit-code handling.
            parameter = "param([string]$Destination = 'Emergency-AI')"
            script = script.replace(parameter, parameter + "\n" + mock_download)
            command = ["cmd", "/d", "/c", name, str(self.root / "installed kit")]
        else:
            mock = self.root / "bin"
            mock.mkdir(exist_ok=True)
            curl = mock / "curl"
            curl.write_text('''#!/bin/sh
[ "$BOOTSTRAP_FAIL" != 1 ] || exit 22
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) out=$2; shift 2 ;;
        *cpython*) source=python.tar.gz; shift ;;
        https:*) source=source.tar.gz; shift ;;
        *) shift ;;
    esac
done
cp "$BOOTSTRAP_FIXTURES/$source" "$out"
''')
            curl.chmod(0o755)
            self.env["PATH"] = str(mock) + os.pathsep + os.environ["PATH"]
            command = ["sh", str(self.root / name), str(self.root / "installed kit")]
        (self.root / name).write_text(script, encoding="utf-8")
        self.env["BOOTSTRAP_FAIL"] = "1" if fail else "0"
        return subprocess.run(command, env=self.env, cwd=self.root, text=True,
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


if __name__ == "__main__":
    unittest.main()
