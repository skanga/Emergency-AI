"""Kiwix selection belongs to a request, never to the shared engine."""
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from app.kiwix import KiwixClient
from app.engine import Engine


class LibraryFilterTests(unittest.TestCase):
    def setUp(self):
        self.client = KiwixClient('http://localhost:8092')
        self.client._books = [{'name': name, 'title': name, 'lang': 'eng'} for name in ('medicine', 'wikipedia')]

    def test_selection_filters_requests_without_changing_catalog(self):
        with patch('app.kiwix.get_text', return_value='<rss/>') as fetch:
            self.client.search('water', book_names=['wikipedia', 'unknown'])
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(parse_qs(urlsplit(fetch.call_args.args[0]).query)['books.name'], ['wikipedia'])
            fetch.reset_mock()
            self.client.search('water')
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(self.client.books()), 2)

    def test_empty_or_stale_selection_searches_no_libraries(self):
        with patch('app.kiwix.get_text') as fetch:
            self.assertEqual(self.client.search('water', book_names=[]), [])
            self.assertEqual(self.client.search('water', book_names=['removed']), [])
            fetch.assert_not_called()

    def test_engine_passes_selection_and_keeps_guides(self):
        engine = Engine.__new__(Engine)
        engine.settings = {}
        engine.kb = Mock()
        engine.kb.search.return_value = []
        engine.kiwix = Mock()
        engine.kiwix.search.return_value = []
        with patch.object(engine, 'kiwix_ok', return_value=True):
            engine.retrieve('water', 'en', kiwix_books=['medicine'])
        engine.kb.search.assert_called_once()
        self.assertEqual(engine.kiwix.search.call_args.kwargs['book_names'], ['medicine'])
