"""Catalog identity must match the name accepted by kiwix-serve."""
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from app.kiwix import KiwixClient

FIXTURES = Path(__file__).parent / 'fixtures' / 'retrieval'
CATALOG = (FIXTURES / 'catalog.xml').read_text()
LOGICAL = 'wikipedia_en_medicine'
SERVED = LOGICAL + '_maxi_2026-10'
RESULT = '<rss><channel><item><title>Burn</title><link>/content/' + SERVED + '/Burn</link></item></channel></rss>'


class CatalogContractTests(unittest.TestCase):
    def response(self, url, **kwargs):
        if '/catalog/' in url:
            return CATALOG
        name = parse_qs(urlsplit(url).query).get('books.name')
        if name != [SERVED]:
            raise HTTPError(url, 400, 'Unknown book', {}, None)
        return RESULT

    def test_logical_selection_uses_advertised_served_name(self):
        client = KiwixClient('http://localhost:8092')
        with patch('app.kiwix.get_text', side_effect=self.response):
            results = client.search('burn', book_names=[LOGICAL])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['book_name'], LOGICAL)
            book = client.books()[0]
            self.assertEqual(book['served_name'], SERVED)
            self.assertTrue(book['archive_uuid'])
            self.assertTrue(book['issued'].startswith('2026-10'))
            self.assertEqual(book['content_url'], '/content/' + SERVED)

    def test_encoded_absolute_and_prefixed_content_links(self):
        for href in ('http://localhost:8092/kiwix/content/' + SERVED,
                     '/kiwix/content/' + SERVED.replace('_', '%5F')):
            xml = CATALOG.replace('/content/' + SERVED, href)
            client = KiwixClient('http://localhost:8092/kiwix')
            with patch('app.kiwix.get_text', side_effect=lambda url, **kw: xml if '/catalog/' in url else self.response(url)):
                self.assertEqual(len(client.search('burn')), 1)

    def test_invalid_content_identity_never_falls_back(self):
        for href in ('https://foreign.invalid/content/' + SERVED, '/search', '/content/../bad',
                     '/content/bad%2Fname', '/content/%252e%252e', '/content/' + SERVED + '/Page'):
            xml = CATALOG.replace('/content/' + SERVED, href)
            client = KiwixClient('http://localhost:8092')
            diagnostics = []
            with patch('app.kiwix.get_text', return_value=xml) as fetch:
                self.assertEqual(client.search('burn', diagnostics=diagnostics), [])
                self.assertEqual(fetch.call_count, 1)
            self.assertEqual(diagnostics[0]['status'], 'identity_error')

    def test_duplicate_logical_names_search_all_editions_and_report_stale(self):
        client = KiwixClient('http://localhost:8092')
        entry = CATALOG[CATALOG.index('<entry>'):CATALOG.index('</entry>') + 8]
        xml = CATALOG.replace('</feed>', entry.replace('2026-10', '2025-10') + '</feed>')
        diagnostics = []
        with patch('app.kiwix.get_text', side_effect=lambda url, **kw: xml if '/catalog/' in url else '<rss/>') as fetch:
            self.assertEqual(client.search('burn', book_names=[LOGICAL, 'removed'], diagnostics=diagnostics), [])
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual([d['status'] for d in diagnostics].count('zero_hits'), 2)
        self.assertEqual([d['status'] for d in diagnostics].count('identity_error'), 1)

    def test_failures_are_distinct_from_successful_zero_hits(self):
        cases = [('<rss/>', 'zero_hits'), ('broken xml', 'parse_error'),
                 ('<html>Error</html>', 'parse_error'),
                 (HTTPError('url', 503, 'Unavailable', {}, None), 'http_error'),
                 (TimeoutError(), 'timeout'), (URLError(TimeoutError()), 'timeout')]
        for response, status in cases:
            client = KiwixClient('http://localhost:8092')
            diagnostics = []
            with patch('app.kiwix.get_text', side_effect=[CATALOG, response]):
                self.assertEqual(client.search('burn', diagnostics=diagnostics), [])
            self.assertEqual(diagnostics[0]['status'], status)

    def test_legacy_name_validated_only_by_success_and_cached(self):
        xml = CATALOG.replace('<link type="text/html" href="/content/' + SERVED + '" />', '')
        client = KiwixClient('http://localhost:8092')
        with patch('app.kiwix.get_text', side_effect=[xml, '<rss/>']):
            self.assertIsNone(client.books()[0]['served_name'])
            client.search('burn')
        self.assertEqual(client.books()[0]['served_name'], LOGICAL)

    def test_empty_selection_needs_no_catalog_and_catalog_failures_are_explicit(self):
        client = KiwixClient('http://localhost:8092')
        with patch('app.kiwix.get_text') as fetch:
            self.assertEqual(client.search('burn', book_names=[]), [])
            fetch.assert_not_called()
        diagnostics = []
        with patch('app.kiwix.get_text', side_effect=OSError('offline')):
            self.assertEqual(client.search('burn', diagnostics=diagnostics), [])
        self.assertEqual(diagnostics[0]['status'], 'catalog_error')

    def test_failed_legacy_validation_does_not_cache_or_search_unrestricted(self):
        xml = CATALOG.replace('<link type="text/html" href="/content/' + SERVED + '" />', '')
        client = KiwixClient('http://localhost:8092')
        diagnostics = []
        with patch('app.kiwix.get_text', side_effect=[xml, HTTPError('url', 400, 'Unknown', {}, None)]) as fetch:
            self.assertEqual(client.search('burn', diagnostics=diagnostics), [])
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(parse_qs(urlsplit(fetch.call_args.args[0]).query)['books.name'], [LOGICAL])
        self.assertIsNone(client.books()[0]['served_name'])
        self.assertEqual(diagnostics[0]['status'], 'identity_error')
        self.assertEqual(diagnostics[0]['failure_status'], 'http_error')
        self.assertEqual(diagnostics[0]['http_status'], 400)

    def test_invalid_catalog_response_is_explicit_and_can_retry(self):
        client = KiwixClient('http://localhost:8092')
        diagnostics = []
        with patch('app.kiwix.get_text', side_effect=['<html>Error</html>', CATALOG, RESULT]):
            self.assertEqual(client.search('burn', diagnostics=diagnostics), [])
            self.assertEqual(diagnostics[0]['status'], 'catalog_error')
            self.assertEqual(len(client.search('burn')), 1)

    def test_catalog_refresh_keeps_saved_logical_selection_after_archive_update(self):
        client = KiwixClient('http://localhost:8092')
        saved_selection = [LOGICAL]
        with patch('app.kiwix.get_text', side_effect=[CATALOG, RESULT]):
            self.assertEqual(len(client.search('burn', book_names=saved_selection)), 1)
        old_uuid = client.books()[0]['archive_uuid']
        new_uuid = '00000000-0000-0000-0000-000000000001'
        updated = CATALOG.replace('2026-10', '2026-11').replace(old_uuid, new_uuid)
        # Engine.kiwix_ok expires this catalog cache every 15 seconds.
        client._books = None
        with patch('app.kiwix.get_text', side_effect=[updated, RESULT]) as fetch:
            self.assertEqual(len(client.search('burn', book_names=saved_selection)), 1)
            self.assertEqual(parse_qs(urlsplit(fetch.call_args.args[0]).query)['books.name'],
                             [LOGICAL + '_maxi_2026-11'])
        self.assertEqual(client.books()[0]['archive_uuid'], new_uuid)
        self.assertEqual(client.books()[0]['name'], LOGICAL)
