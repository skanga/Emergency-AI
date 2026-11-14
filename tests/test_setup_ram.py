"""RAM guidance and the smallest-model setup default."""
import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch, mock_open

from app import prepare


class SetupRamTests(unittest.TestCase):
    def test_enter_selects_smallest_with_ram_guidance(self):
        for ram, expected in [(16 * 1024**3, 'System RAM: 16.0 GiB'),
                              (None, 'System RAM: could not detect')]:
            with self.subTest(ram=ram), tempfile.TemporaryDirectory() as runtime, \
                    patch.object(prepare, 'RUNTIME_DIR', runtime), \
                    patch.object(prepare, 'system_ram_bytes', return_value=ram, create=True), \
                    patch.object(prepare, 'get_model', return_value=True) as download, \
                    patch('builtins.input', side_effect=['', '', 'none', 'this', 'n', 'y']), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(prepare.run(skip_tools=True), 0)
                self.assertEqual(download.call_args.args[0]['id'], 'lfm3-1.7b')
                self.assertIn(expected, output.getvalue())
                self.assertIn('8 GB RAM recommended', output.getvalue())
                if ram:
                    self.assertIn('meets RAM recommendation', output.getvalue())
                    self.assertIn('below RAM recommendation', output.getvalue())

    def test_linux_total_memory(self):
        with patch.object(prepare.sys, 'platform', 'linux'), \
                patch('builtins.open', mock_open(read_data='MemTotal:       8388608 kB\nMemFree: 100 kB\n')):
            self.assertEqual(prepare.system_ram_bytes(), 8 * 1024**3)

    def test_macos_total_memory(self):
        with patch.object(prepare.sys, 'platform', 'darwin'), \
                patch.object(prepare.subprocess, 'check_output', return_value='17179869184\n'):
            self.assertEqual(prepare.system_ram_bytes(), 16 * 1024**3)

    def test_detection_failure_is_optional(self):
        with patch.object(prepare.sys, 'platform', 'linux'), \
                patch('builtins.open', side_effect=OSError):
            self.assertIsNone(prepare.system_ram_bytes())

    def test_windows_total_memory(self):
        import ctypes
        def fill_memory(pointer):
            pointer._obj.total_physical = 16 * 1024**3
            return 1
        with patch.object(prepare.sys, 'platform', 'win32'), \
                patch.object(ctypes, 'windll', create=True) as windll:
            windll.kernel32.GlobalMemoryStatusEx.side_effect = fill_memory
            self.assertEqual(prepare.system_ram_bytes(), 16 * 1024**3)
            windll.kernel32.GlobalMemoryStatusEx.side_effect = None
            windll.kernel32.GlobalMemoryStatusEx.return_value = 0
            self.assertIsNone(prepare.system_ram_bytes())
