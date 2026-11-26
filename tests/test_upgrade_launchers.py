"""Execute the host launcher with maintenance arguments and paths containing spaces."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class UpgradeLauncherTests(unittest.TestCase):
    def test_native_launcher_forwards_upgrade_arguments(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='Emergency launcher ') as temp:
            root = Path(temp)
            for name in ('run.sh', 'run.command', 'run.bat', 'upgrade_recovery.py'):
                shutil.copy2(source / name, root / name)
            (root / 'emergency.py').write_text('import json, sys\nprint(json.dumps(sys.argv[1:]))\n', encoding='utf-8')
            arguments = ['--check-updates', '--root', str(root / 'other installation'), '--json']
            if os.name == 'nt':
                # Pass the batch path as one command, retaining cmd.exe's outer quotes.
                command = 'cmd.exe /d /s /c ""' + str(root / 'run.bat') + '" ' + subprocess.list2cmdline(arguments) + '"'
            else:
                launcher = 'run.command' if sys.platform == 'darwin' else 'run.sh'
                command = ['sh', str(root / launcher), *arguments]
            result = subprocess.run(command, cwd=temp, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            actual = next(line for line in result.stdout.splitlines() if line.startswith('['))
            self.assertEqual(json.loads(actual), arguments)
