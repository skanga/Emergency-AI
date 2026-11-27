import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import prepare
from app.kiwix import KiwixClient
import emergency


class ReviewFixTests(unittest.TestCase):
    def test_search_includes_seventh_library(self):
        client = KiwixClient('http://localhost:8092')
        client._books = [{'name': str(i), 'title': str(i), 'lang': 'eng'} for i in range(7)]
        def response(url, **kwargs):
            return ('<rss><item><title>Water</title><link>/content/6/water</link></item></rss>'
                    if 'books.name=6' in url else '<rss/>')
        with patch('app.kiwix.get_text', side_effect=response):
            self.assertEqual(client.search('water')[0]['book_name'], '6')

    def test_complete_partial_is_promoted_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = str(Path(folder) / 'model')
            data = b'complete verified file'
            Path(dest + '.part').write_bytes(data)
            with patch('app.downloads._download_urllib', return_value=False) as fetch, patch('app.prepare.shutil.which', return_value=None):
                prepare.download('https://example.invalid/model', dest, len(data), hashlib.sha256(data).hexdigest())
                fetch.assert_not_called()
            self.assertEqual(Path(dest).read_bytes(), data)

    def test_cli_disabled_backend_does_not_start_model(self):
        launcher = Mock(procs=[])
        with patch('app.launcher.Launcher', return_value=launcher), patch('app.engine.Engine'), patch('app.startup.load_selection', return_value=None):
            emergency._engine_with_launcher(SimpleNamespace(no_engines=False), {'llm_backend': 'none'})
        launcher.start_llm.assert_not_called()

    def test_cli_uses_saved_model_selection(self):
        settings = {'llm_backend': 'none'}
        with patch('app.launcher.Launcher', return_value=Mock(procs=[])), patch('app.engine.Engine'), patch('app.startup.load_selection', return_value={'model': 'chosen'}), patch('app.startup.load_json', return_value={'models': [{'id': 'chosen', 'file': 'chosen.gguf'}]}):
            emergency._engine_with_launcher(SimpleNamespace(no_engines=False), settings)
        self.assertEqual(settings['model_file'], 'chosen.gguf')

    def test_late_relevant_result_beats_early_unrelated_results(self):
        client = KiwixClient('http://localhost:8092')
        client._books = [{'name': str(i), 'title': str(i), 'lang': 'eng'} for i in range(7)]
        def response(url, **kwargs):
            title = 'Water treatment' if 'books.name=6' in url else 'Unrelated'
            return f'<rss><item><title>{title}</title><link>/content/book/page</link></item></rss>'
        with patch('app.kiwix.get_text', side_effect=response):
            self.assertEqual(client.search('water treatment', limit=1)[0]['book_name'], '6')

    def test_invalid_complete_partial_is_not_promoted(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = str(Path(folder) / 'model')
            Path(dest + '.part').write_bytes(b'wrong')
            with patch('app.downloads._download_urllib', return_value=False), patch('app.prepare.shutil.which', return_value=None):
                with self.assertRaises(RuntimeError):
                    prepare.download('https://example.invalid/model', dest, 5, hashlib.sha256(b'right').hexdigest())
            self.assertFalse(Path(dest).exists())

    def test_browser_completion_and_interruption_history(self):
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('Node required')
        subprocess.run(['node', 'tests/test_stream_completion.js'], cwd=Path(__file__).resolve().parents[1], check=True, timeout=10)
