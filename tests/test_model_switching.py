"""Model lifecycle, inference coordination and HTTP switching contracts."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from app import config, launcher, server
from app.models import ModelManager


class ModelSwitchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('first.gguf', 'second.gguf', 'split-00002-of-00003.gguf'):
            (self.root / name).write_bytes(b'GGUF')
        (self.root / 'empty.gguf').touch()
        self.settings = {'model_file': 'first.gguf'}
        self.engine = Mock(settings=self.settings)
        self.launcher = Mock(settings=self.settings, llm_model='first.gguf', llm_process=None)
        self.launcher.start_llm.return_value = True
        self.paths = patch('app.models.MODELS_DIR', str(self.root))
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.binary = patch('app.models.find_llama_server', return_value=('llama-server', 'llama.cpp'))
        self.binary.start()
        self.addCleanup(self.binary.stop)
        self.port = patch('app.models.port_in_use', return_value=False)
        self.port.start()
        self.addCleanup(self.port.stop)
        self.persist = patch('app.models.save_local_settings')
        self.save = self.persist.start()
        self.addCleanup(self.persist.stop)
        self.manager = ModelManager(self.engine, self.launcher)

    def test_only_loadable_installed_filenames_can_be_selected(self):
        self.assertEqual([m['file'] for m in self.manager.status()['models']], ['first.gguf', 'second.gguf'])
        for value in ('../second.gguf', str(self.root / 'second.gguf'), 'missing.gguf', '', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.manager.request(value)
        self.launcher.stop_llm.assert_not_called()

    def test_switch_waits_for_answer_then_unloads_before_loading_and_persists(self):
        self.assertTrue(self.manager.begin_answer())
        entered, release = threading.Event(), threading.Event()
        order = []
        self.launcher.stop_llm.side_effect = lambda: order.append('stop')
        self.launcher.start_llm.side_effect = lambda filename: order.append('start') or True

        def ready():
            entered.set()
            self.assertTrue(release.wait(3))

        with patch.object(self.manager, '_wait_ready', side_effect=ready):
            self.assertEqual(self.manager.request('second.gguf')['phase'], 'queued')
            self.launcher.stop_llm.assert_not_called()
            self.assertFalse(self.manager.begin_answer())
            self.manager.end_answer()
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.manager.status()['phase'], 'loading')
                with self.assertRaises(RuntimeError):
                    self.manager.request('first.gguf')
                self.assertFalse(self.manager.begin_answer())
            finally:
                release.set()
                self.manager.worker.join(4)
        self.assertEqual(order, ['stop', 'start'])
        self.assertEqual(self.manager.status()['active'], 'second.gguf')
        self.save.assert_called_once_with({'model_file': 'second.gguf'})
        self.engine.reset_llm.assert_called()
        self.assertTrue(self.manager.begin_answer())
        self.manager.end_answer()

    def test_failed_load_stops_process_and_does_not_save_bad_choice(self):
        with patch.object(self.manager, '_wait_ready', side_effect=RuntimeError('load failed')):
            self.manager.request('second.gguf')
            self.manager.worker.join(3)
        state = self.manager.status()
        self.assertEqual(state['phase'], 'error')
        self.assertIsNone(state['active'])
        self.assertIn('load failed', state['error'])
        self.assertEqual(self.settings['model_file'], 'first.gguf')
        self.save.assert_not_called()
        self.assertEqual(self.launcher.stop_llm.call_count, 2)

    def test_external_or_disabled_engine_cannot_be_restarted(self):
        for changes in ({'llm_backend': 'ollama'}, {'llm_backend': 'none'},
                        {'llm_url': 'https://example.com/v1'}, {'llm_url': 'http://127.0.0.1:9999/v1'}):
            with self.subTest(changes=changes):
                self.settings.clear()
                self.settings.update(changes)
                self.assertFalse(self.manager.status()['enabled'])
                with self.assertRaises(RuntimeError):
                    self.manager.request('second.gguf')
        self.settings.clear()
        with patch('app.models.port_in_use', return_value=True):
            self.assertFalse(self.manager.status()['enabled'])
        self.launcher.stop_llm.assert_not_called()

    def test_readiness_failure_when_child_exits(self):
        self.launcher.llm_process = Mock()
        self.launcher.llm_process.poll.return_value = 1
        with self.assertRaises(RuntimeError):
            self.manager._wait_ready()
        self.assertEqual(self.manager.status()['phase'], 'error')
        self.assertIsNone(self.manager.status()['active'])

    def test_readiness_waits_for_health_instead_of_an_open_port(self):
        self.launcher.llm_process = Mock()
        self.launcher.llm_process.poll.return_value = None
        with patch('app.models.get_json', side_effect=[OSError('loading'), {'status': 'ok'}]) as health:
            self.manager._wait_ready()
        self.assertEqual(health.call_count, 2)

    def test_persistence_failure_leaves_a_retryable_error(self):
        self.save.side_effect = OSError('disk full')
        with patch.object(self.manager, '_wait_ready'):
            self.manager.request('second.gguf')
            self.manager.worker.join(3)
        self.assertEqual(self.manager.status()['phase'], 'error')
        self.assertEqual(self.settings['model_file'], 'first.gguf')
        self.assertTrue(self.manager.begin_answer())
        self.manager.end_answer()

    def test_close_cancels_a_queued_switch_without_starting_a_model(self):
        self.assertTrue(self.manager.begin_answer())
        self.manager.request('second.gguf')
        self.manager.close()
        self.assertFalse(self.manager.worker.is_alive())
        self.launcher.start_llm.assert_not_called()

    def test_switch_api_and_origin_validation(self):
        httpd = server.serve(self.engine, self.settings, '127.0.0.1', 0, models=self.manager)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        def request(method, path, body=None, origin=None):
            conn = http.client.HTTPConnection(*httpd.server_address, timeout=3)
            headers = {'Content-Type': 'application/json'}
            if origin:
                headers['Origin'] = origin
            try:
                conn.request(method, path, json.dumps(body) if body is not None else None, headers)
                response = conn.getresponse()
                return response.status, json.loads(response.read())
            finally:
                conn.close()

        self.assertEqual(request('GET', '/api/models')[0], 200)
        self.assertEqual(request('POST', '/api/models', {'model': '../bad.gguf'})[0], 400)
        self.assertEqual(request('POST', '/api/models', {'model': 'second.gguf'}, 'https://other.example')[0], 403)
        self.assertTrue(self.manager.begin_answer())
        try:
            code, state = request('POST', '/api/models', {'model': 'second.gguf'})
            self.assertEqual(code, 202)
            self.assertEqual(state['phase'], 'queued')
            self.assertEqual(request('POST', '/api/ask', {'q': 'hello'})[0], 503)
            self.assertEqual(request('POST', '/api/models', {'model': 'first.gguf'})[0], 409)
        finally:
            with patch.object(self.manager, '_wait_ready'):
                self.manager.end_answer()
                self.manager.worker.join(3)


class OwnedProcessTests(unittest.TestCase):
    def test_stopping_model_keeps_kiwix_and_waits_for_killed_child(self):
        engines = launcher.Launcher({})
        llm, kiwix = Mock(), Mock()
        llm.poll.return_value = None
        llm.wait.side_effect = [TimeoutError(), 0]
        engines.llm_process = llm
        engines.procs = [llm, kiwix]
        engines.stop_llm()
        llm.kill.assert_called_once()
        self.assertEqual(llm.wait.call_count, 2)
        kiwix.terminate.assert_not_called()
        self.assertEqual(engines.procs, [kiwix])

    def test_model_preference_survives_reload_and_preserves_other_local_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.local.json'
            path.write_text('{"llm_threads": 8}', encoding='utf-8')
            with patch.object(config, 'CONFIG_DIR', folder), patch.object(config, 'LOCAL_SETTINGS_FILE', str(path)):
                config.save_local_settings({'model_file': 'second.gguf'})
                saved = config.load_settings()
            self.assertEqual(saved['model_file'], 'second.gguf')
            self.assertEqual(saved['llm_threads'], 8)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['settings.local.json'])


if __name__ == '__main__':
    unittest.main()
