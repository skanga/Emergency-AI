"""Startup reuses only our server and preserves CLI subcommands and text."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import Mock, patch

import emergency


class StartCommandTests(unittest.TestCase):
    def test_offline_web_server_does_not_require_reverse_dns(self):
        from app.server import serve
        with patch("socket.getfqdn", side_effect=OSError("DNS unavailable")):
            server = serve(Mock(), {}, port=0)
            server.server_close()

    def test_fresh_offline_kit_serves_guides_and_second_start_reuses_it(self):
        with tempfile.TemporaryDirectory(prefix="Emergency fresh kit ") as folder:
            root = Path(folder)
            source = Path(emergency.__file__).parent
            for name in ("app", "config", "web", "knowledge"):
                shutil.copytree(source / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "settings.local.json"))
            shutil.copy2(source / "emergency.py", root / "emergency.py")
            settings = root / "config" / "settings.json"
            cfg = json.loads(settings.read_text(encoding="utf-8"))
            cfg.update(llm_backend="none", kiwix_enabled=False)
            settings.write_text(json.dumps(cfg), encoding="utf-8")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            command = [sys.executable, "-B", "-u", str(root / "emergency.py"), "--no-browser", "--port", str(port)]
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                url = f"http://127.0.0.1:{port}/api/guides?lang=en"
                deadline = time.monotonic() + 30
                while True:
                    try:
                        with opener.open(url, timeout=1) as response:
                            guides = json.load(response)
                        break
                    except OSError:
                        if proc.poll() is not None or time.monotonic() >= deadline:
                            proc.terminate()
                            log, _ = proc.communicate(timeout=10)
                            self.fail("Fresh kit did not open its guide interface:\n" + log.decode("utf-8", "replace"))
                        time.sleep(0.1)
                self.assertTrue(guides)
                self.assertFalse((root / "runtime" / "setup.json").exists())
                again = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
                self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
                self.assertIn(b"UI already running", again.stdout)
            finally:
                proc.terminate()
                output, _ = proc.communicate(timeout=10)
            self.assertIn(b"No interactive terminal", output)

    def test_default_start_options_and_prepare_resume(self):
        for argv, command in ((["--no-browser"], "cmd_start"),
                              (["prepare", "--resume"], "cmd_prepare"),
                              (["ask", "how", "to", "start"], "cmd_ask")):
            with self.subTest(argv=argv), patch("sys.argv", ["emergency.py"] + argv), \
                    patch.object(emergency, command, return_value=0) as handler:
                self.assertEqual(emergency.main(), 0)
                args = handler.call_args.args[0]
                if command == "cmd_ask":
                    self.assertEqual(args.text, ["how", "to", "start"])
                if command == "cmd_prepare":
                    self.assertTrue(args.resume)

    def test_local_only_option_selects_loopback(self):
        with patch('sys.argv', ['emergency.py', '--local-only']), patch.object(emergency, 'cmd_start', return_value=0) as start:
            self.assertEqual(emergency.main(), 0)
        self.assertEqual(start.call_args.args[0].host, '127.0.0.1')

    def test_default_server_binds_all_interfaces(self):
        from app.server import serve
        httpd = serve(Mock(), {}, port=0)
        self.addCleanup(httpd.server_close)
        self.assertEqual(httpd.server_address[0], '0.0.0.0')

    def test_connection_info_uses_real_bound_port_and_lan_address(self):
        output = io.StringIO()
        with patch.object(emergency, 'lan_ip', return_value='192.168.10.25'):
            emergency.print_connection_info('0.0.0.0', 45678, 'en', output)
        self.assertIn('http://127.0.0.1:45678/?lang=en', output.getvalue())
        self.assertIn('http://192.168.10.25:45678/?lang=en', output.getvalue())
        self.assertNotIn('http://0.0.0.0', output.getvalue())
        self.assertIn('\u2588', output.getvalue())

    def test_local_only_and_missing_network_do_not_print_misleading_qr(self):
        for host, ip in (('127.0.0.1', '192.168.10.25'), ('0.0.0.0', None)):
            output = io.StringIO()
            with self.subTest(host=host), patch.object(emergency, 'lan_ip', return_value=ip):
                emergency.print_connection_info(host, 8090, 'en', output)
            self.assertNotIn('\u2588', output.getvalue())
            self.assertNotIn('http://0.0.0.0', output.getvalue())

    def test_existing_server_cannot_silently_ignore_local_only_option(self):
        args = argparse.Namespace(lang='en', host='127.0.0.1', port=8090, no_browser=True, no_engines=True)
        response = Mock()
        response.headers = {'Server': 'Emergency-AI/1.0', 'X-Emergency-AI-Bind': '0.0.0.0'}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        output = io.StringIO()
        with patch('app.launcher.port_in_use', return_value=True), patch('app.net.open_url', return_value=response), \
                patch.object(emergency, 'lan_ip', return_value='192.168.10.25'), contextlib.redirect_stdout(output):
            self.assertEqual(emergency.cmd_start(args, {}), 1)
        self.assertIn('restart', output.getvalue())
        self.assertNotIn('192.168.10.25', output.getvalue())
        self.assertNotIn('\u2588', output.getvalue())

    def test_occupied_port_checked_before_setup_or_engine_launch(self):
        args = argparse.Namespace(lang="en", host=None, port=8090, no_browser=True, no_engines=False)
        for server_name, expected in (("Emergency-AI/1.0", 0), ("Survival-AI/1.0", 1), ("UnrelatedService/1.0", 1)):
            response = Mock()
            response.headers = {"Server": server_name, "X-Emergency-AI-Bind": "0.0.0.0"}
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            with self.subTest(server=server_name), contextlib.redirect_stdout(io.StringIO()), \
                    patch("app.launcher.port_in_use", return_value=True), \
                    patch("app.net.open_url", return_value=response), \
                    patch("app.server.serve", side_effect=OSError("occupied")), \
                    patch("app.startup.ensure_ready") as setup, patch("app.launcher.Launcher") as launcher:
                self.assertEqual(emergency.cmd_start(args, {}), expected)
                setup.assert_not_called()
                launcher.assert_not_called()
