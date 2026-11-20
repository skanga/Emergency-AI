"""Exercise installer destination selection without downloading anything."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerDestinationTests(unittest.TestCase):
    def select(self, platform, cwd, argument=None):
        if platform == "windows":
            if os.name != "nt":
                self.skipTest("PowerShell required")
            source = (ROOT / "install.bat").read_text().split("# POWERSHELL\n", 1)[1]
            source = source.split("    $parent = Split-Path -Parent $target", 1)[0]
            source += '\nWrite-Output $target\n} catch { throw }'
            # The batch wrapper passes an empty destination when no argument is given.
            quoted = (argument or "").replace("'", "''")
            command = f"& {{ {source} }} -Destination '{quoted}'"
            args = ["powershell.exe", "-NoProfile", "-Command", command]
        else:
            shell = shutil.which("sh")
            if not shell:
                self.skipTest("POSIX shell required")
            source = (ROOT / "install.sh").read_text().split("\ncheck_destination\n", 1)[0]
            source += '\nprintf "%s\\n" "$destination"\n'
            args = [shell, "-c", source, "install.sh"]
            if argument is not None:
                args.append(argument)
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)
        selected = result.stdout.strip()
        if platform == "posix" and os.name == "nt" and selected.startswith("/"):
            selected = subprocess.check_output(
                [shutil.which("sh"), "-c", 'cygpath -w "$1"', "sh", selected], text=True
            ).strip()
        return Path(os.path.join(cwd, selected)).resolve()

    def test_default_and_explicit_destinations(self):
        for platform in ("windows", "posix"):
            with tempfile.TemporaryDirectory() as tmp:
                # Resolve macOS /var aliases and Windows short directory names.
                current = Path(tmp).resolve()
                with self.subTest(platform=platform, case="empty"):
                    self.assertEqual(self.select(platform, tmp), current)
                (current / "install.sh").touch()
                with self.subTest(platform=platform, case="installer only"):
                    self.assertEqual(self.select(platform, tmp), current)
                with self.subTest(platform=platform, case="explicit"):
                    self.assertEqual(self.select(platform, tmp, "custom"), current / "custom")
                (current / '.downloads').mkdir()
                with self.subTest(platform=platform, case="retry with cache"):
                    self.assertEqual(self.select(platform, tmp), current)
                (current / "personal.txt").touch()
                with self.subTest(platform=platform, case="populated"):
                    self.assertEqual(self.select(platform, tmp), current / "Emergency-AI")
                named = current / "Emergency-AI"
                named.mkdir()
                (named / "personal.txt").touch()
                with self.subTest(platform=platform, case="named"):
                    self.assertEqual(self.select(platform, str(named)), named)

    @unittest.skipUnless(os.name == "nt", "Windows drive root")
    def test_windows_root_selection_without_writing_to_drive(self):
        root = Path(ROOT.anchor)
        self.assertEqual(self.select("windows", str(root)), root)

    def test_posix_root_selection_without_writing_to_drive(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX shell required")
        source = (ROOT / "install.sh").read_text().split("\ncheck_destination\n", 1)[0]
        result = subprocess.run(
            [shell, "-c", 'cd /\n' + source + '\nprintf "%s\\n" "$destination"'],
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "/")


if __name__ == "__main__":
    unittest.main()
