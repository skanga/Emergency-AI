"""Kiwix source links stay on the configured offline service."""

import unittest
from unittest.mock import patch

from app.kiwix import KiwixClient


class KiwixLinkTests(unittest.TestCase):
    def test_result_without_article_link_is_ignored(self):
        client = KiwixClient("http://localhost:8092")
        client._books = [{"name": "book", "title": "Book", "lang": "eng"}]
        with patch("app.kiwix.get_text", return_value='<rss><item><title>Missing link</title></item></rss>'):
            self.assertEqual(client.search("page"), [])

    def test_absolute_search_result_is_normalized(self):
        client = KiwixClient("http://localhost:8092")
        client._books = [{"name": "book", "title": "Book", "lang": "eng"}]
        xml = '<rss><channel><item><title>Page</title><link>http://localhost:8092/content/book/Page?q=1</link></item></channel></rss>'
        with patch("app.kiwix.get_text", return_value=xml):
            self.assertEqual(client.search("page")[0]["link"], "/content/book/Page?q=1")

    def test_foreign_article_link_is_not_fetched(self):
        client = KiwixClient("http://localhost:8092")
        with patch("app.kiwix.get_text") as fetch:
            self.assertEqual(client.article_text("https://untrusted.example/article"), "")
            fetch.assert_not_called()
