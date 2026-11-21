from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import launcher


CATALOG = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><name>medicine</name></entry></feed>'
ADDRESS_ERROR = 'ERROR: IP address is not available on this system: 127.0.0.1\n'


class KiwixStartupTests(unittest.TestCase):
    def setUp(self):
        self.logs = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(launcher, 'LOG_DIR', str(self.logs)))
        self.messages = []
        self.app = launcher.Launcher({}, say=self.messages.append)
        self.enterContext(patch.object(launcher, '_ensure_exec'))
        self.enterContext(patch.object(launcher, '_is_wsl', return_value=True))
        self.port = self.enterContext(patch.object(launcher, 'port_in_use', return_value=False))
        self.enterContext(patch.object(launcher, 'find_zims', return_value=['/kit/medicine.zim']))
        self.enterContext(patch.object(launcher, 'find_kiwix_serve', return_value='/kit/kiwix-serve'))
        self.http = self.enterContext(patch.object(launcher, 'get_text', create=True, return_value=CATALOG))
        self.spawn = self.enterContext(patch.object(launcher, '_spawn'))
        self.process = self.make_process()
        self.spawn.return_value = self.process
        self.clock = 0.0
        self.enterContext(patch.object(launcher.time, 'monotonic', side_effect=lambda: self.clock))
        self.enterContext(patch.object(launcher.time, 'sleep', side_effect=self.advance))

    def advance(self, seconds):
        self.clock += seconds

    def make_process(self, code=None):
        process = Mock()
        process.poll.return_value = code
        process.wait.return_value = code or 0
        process.terminate.side_effect = lambda: setattr(process.poll, 'return_value', 0)
        return process

    def assert_ready(self):
        self.assertIn('Kiwix ready', '\n'.join(self.messages))
        self.assertIn('/catalog/v2/entries?count=1', self.http.call_args.args[0])

    def test_success_requires_catalog_response_and_retains_owned_process(self):
        self.assertTrue(self.app.start_kiwix())
        self.assert_ready()
        self.assertEqual(self.app.procs, [self.process])
        self.assertEqual(self.spawn.call_args.args[0][1:3], ['--address', '127.0.0.1'])
        self.app.stop()
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called_once()

    def test_startup_waits_until_http_ready(self):
        self.http.side_effect = [OSError('not ready'), CATALOG]
        self.assertTrue(self.app.start_kiwix())
        self.assertGreater(self.clock, 0)
        self.assert_ready()

    def test_exact_wsl_address_error_retries_once_on_ipv4(self):
        failed = self.make_process(1)

        def spawn(command, logname):
            if command[2] == '127.0.0.1':
                (self.logs / logname).write_text(ADDRESS_ERROR)
                return failed
            return self.process

        self.spawn.side_effect = spawn
        self.assertTrue(self.app.start_kiwix())
        self.assertEqual(self.spawn.call_count, 2)
        self.assertEqual(self.spawn.call_args.args[0][1:3], ['--address', 'ipv4'])
        self.assertEqual(self.app.procs, [self.process])
        failed.wait.assert_called_once()
        self.assertIn('all IPv4 interfaces', '\n'.join(self.messages))
        self.assert_ready()

    def test_non_wsl_does_not_broaden_binding(self):
        def spawn(*args):
            (self.logs / 'kiwix.log').write_text(ADDRESS_ERROR)
            return self.make_process(1)
        self.spawn.side_effect = spawn
        with patch.object(launcher, '_is_wsl', return_value=False):
            self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_called_once()

    def test_retry_failure_is_reported_without_further_retry(self):
        def spawn(command, logname):
            with (self.logs / logname).open('a') as log:
                log.write(ADDRESS_ERROR if command[2] == '127.0.0.1' else 'bind failed\n')
            return self.make_process(1)
        self.spawn.side_effect = spawn
        self.assertFalse(self.app.start_kiwix())
        self.assertEqual(self.spawn.call_count, 2)
        self.assertEqual(self.app.procs, [])
        self.assertNotIn('Kiwix ready', '\n'.join(self.messages))

    def test_stale_address_error_does_not_trigger_retry(self):
        (self.logs / 'kiwix.log').write_text(ADDRESS_ERROR)
        self.spawn.return_value = self.make_process(1)
        self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_called_once()
        self.assertIn('logs/kiwix.log', '\n'.join(self.messages))

    def test_other_failure_does_not_trigger_retry(self):
        for error in ['Unable to add the ZIM file', 'Address already in use',
                      'ERROR: IP address is not available on this system: 127.0.0.10\n']:
            with self.subTest(error=error):
                self.spawn.reset_mock()
                def spawn(*args):
                    with (self.logs / 'kiwix.log').open('a') as log:
                        log.write(error)
                    return self.make_process(1)
                self.spawn.side_effect = spawn
                self.assertFalse(self.app.start_kiwix())
                self.spawn.assert_called_once()

    def test_timeout_stops_child_without_retry_or_success_message(self):
        self.http.side_effect = OSError('connection refused')
        self.assertFalse(self.app.start_kiwix())
        self.assertLessEqual(self.clock, 30.5)
        self.assertGreaterEqual(self.clock, 30)
        self.process.terminate.assert_called_once()
        self.assertEqual(self.app.procs, [])
        self.spawn.assert_called_once()
        self.assertIn('timed out', '\n'.join(self.messages))

    def test_existing_kiwix_is_reused_without_taking_ownership(self):
        self.port.return_value = True
        self.assertTrue(self.app.start_kiwix())
        self.http.assert_called_once()
        self.spawn.assert_not_called()
        self.app.stop()
        self.assertEqual(self.app.procs, [])

    def test_occupied_port_must_serve_valid_atom_catalog(self):
        self.port.return_value = True
        for body in ['<html>other service</html>', 'invalid xml', '<feed/>']:
            with self.subTest(body=body):
                self.http.return_value = body
                self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_not_called()

    def test_missing_executable_is_reported(self):
        self.spawn.side_effect = FileNotFoundError('binary missing')
        self.assertFalse(self.app.start_kiwix())
        self.assertIn('binary missing', '\n'.join(self.messages))

    def test_exit_during_http_probe_is_not_success(self):
        def response(*args, **kwargs):
            self.process.poll.return_value = 1
            return CATALOG
        self.http.side_effect = response
        self.assertFalse(self.app.start_kiwix())
        self.assertNotIn('Kiwix ready', '\n'.join(self.messages))

    def test_ctrl_c_during_startup_cleans_up_kiwix_and_existing_ai(self):
        ai = self.make_process()
        self.app.procs.append(ai)
        self.http.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.app.start_kiwix()
        self.assertEqual(self.app.procs, [])
        ai.terminate.assert_called_once()
        self.process.terminate.assert_called_once()

    def test_concurrent_stop_cancels_wait_without_retry(self):
        def stop(*args, **kwargs):
            self.app.stop()
            return CATALOG
        self.http.side_effect = stop
        self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_called_once()
        self.assertEqual(self.app.procs, [])

    def test_cleanup_failure_does_not_start_duplicate_server(self):
        self.http.side_effect = OSError('not ready')
        self.process.wait.side_effect = subprocess.TimeoutExpired('kiwix-serve', 5)
        self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_called_once()
        self.assertIn(self.process, self.app.procs)
        self.assertIn('Could not stop', '\n'.join(self.messages))

    def test_stop_at_retry_boundary_prevents_restart(self):
        def spawn(*args):
            (self.logs / 'kiwix.log').write_text(ADDRESS_ERROR)
            return self.make_process(1)
        self.spawn.side_effect = spawn

        def say(message):
            self.messages.append(message)
            if 'retrying on all IPv4' in message:
                self.app.stop()
        self.app.say = say
        self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_called_once()
        self.assertEqual(self.app.procs, [])

    def test_stop_during_spawn_reaps_new_child(self):
        def spawn(*args):
            self.app.stop()
            return self.process
        self.spawn.side_effect = spawn
        self.assertFalse(self.app.start_kiwix())
        self.spawn.assert_called_once()
        self.process.terminate.assert_called_once()
        self.assertEqual(self.app.procs, [])


if __name__ == '__main__':
    unittest.main()
