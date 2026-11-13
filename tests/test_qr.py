"""Terminal QR geometry and offline LAN discovery."""
import unittest
from unittest.mock import Mock, patch

import emergency
from app.qr import terminal_qr


class TerminalQRTests(unittest.TestCase):
    def test_compact_qr_preserves_quiet_zone_and_console_colors(self):
        url = 'http://192.168.10.25:45678/?lang=en'
        plain = terminal_qr(url)
        rows = plain.splitlines()
        self.assertTrue(all(len(row) == len(rows[0]) for row in rows))
        self.assertLess(len(rows[0]), 80)
        self.assertTrue(all(row[:4] == row[-4:] == '    ' for row in rows))
        self.assertTrue(all(not row.strip() for row in rows[:2] + rows[-2:]))
        self.assertNotIn('\x1b', plain)
        colored = terminal_qr(url, color=True).splitlines()
        self.assertTrue(all(row.startswith('\x1b[30;47m') and row.endswith('\x1b[0m') for row in colored))

    def test_lan_discovery_falls_back_without_a_default_route(self):
        sock = Mock()
        sock.__enter__ = Mock(return_value=sock)
        sock.__exit__ = Mock(return_value=False)
        sock.connect.side_effect = OSError('no default route')
        addresses = [(None, None, None, None, (ip, 0)) for ip in ('127.0.0.1', '169.254.1.2', '192.168.4.25')]
        with patch('socket.socket', return_value=sock), patch('socket.getaddrinfo', return_value=addresses):
            self.assertEqual(emergency.lan_ip(), '192.168.4.25')

    def test_no_lan_when_only_loopback_is_available(self):
        with patch('socket.socket', side_effect=OSError('offline')), patch('socket.getaddrinfo', side_effect=OSError('offline')):
            self.assertIsNone(emergency.lan_ip())
