"""Deterministic cache interleavings, with no real network requests."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest
from unittest.mock import patch

from app.engine import Engine
from app.kiwix import KiwixClient
from app.llm import LLMError

XML = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><name>book</name><title>Book</title><language>eng</language></entry></feed>'


class CacheThreadTests(unittest.TestCase):
    def test_concurrent_readers_share_refresh_and_receive_copies(self):
        client = KiwixClient('http://local')
        entered = threading.Event(); release = threading.Event(); second = threading.Event()
        def fetch(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return XML
        def reader():
            second.set()
            return client.books()
        with patch('app.kiwix.get_text', side_effect=fetch) as request, ThreadPoolExecutor(2) as pool:
            one = pool.submit(client.books)
            self.assertTrue(entered.wait(2))
            two = pool.submit(reader)
            self.assertTrue(second.wait(2))
            release.set()
            first, other = one.result(2), two.result(2)
        self.assertEqual(request.call_count, 1)
        first[0]['title'] = 'changed'
        self.assertEqual(other[0]['title'], 'Book')
        self.assertEqual(client.books()[0]['title'], 'Book')

    def test_invalidation_during_refresh_keeps_returned_snapshot_valid(self):
        client = KiwixClient('http://local')
        entered = threading.Event(); release = threading.Event(); invalidating = threading.Event()
        def fetch(*args, **kwargs):
            entered.set(); self.assertTrue(release.wait(2)); return XML
        def invalidate():
            invalidating.set(); client.invalidate_catalog()
        with patch('app.kiwix.get_text', side_effect=fetch) as request, ThreadPoolExecutor(2) as pool:
            reading = pool.submit(client.books)
            self.assertTrue(entered.wait(2))
            invalidation = pool.submit(invalidate)
            self.assertTrue(invalidating.wait(2))
            release.set()
            snapshot = reading.result(2); invalidation.result(2)
            self.assertEqual(snapshot[0]['title'], 'Book')
            self.assertEqual(client.books()[0]['title'], 'Book')
            self.assertEqual(request.call_count, 2)

    def test_success_clears_previous_failure_and_diagnostics_stay_with_caller(self):
        client = KiwixClient('http://local'); failed = []; good = []
        with patch('app.kiwix.get_text', side_effect=[OSError('offline'), XML]):
            self.assertEqual(client.books(diagnostics=failed), [])
            self.assertEqual(client.books(diagnostics=good)[0]['title'], 'Book')
        self.assertEqual(failed[0]['status'], 'catalog_error')
        self.assertEqual(good, [])
        self.assertIsNone(client._catalog_error)
        self.assertIsNone(client._catalog_failure)

    def test_old_generation_failure_does_not_invalidate_new_client(self):
        engine = Engine({'kiwix_enabled':False})
        replacement = object()
        class Client:
            def options(self): return dict(context=10000, max_tokens=100, context_margin=100)
            def count_prompt(self, messages): return 10
            def describe(self): return {'backend':'test'}
            def stream_chat(self, messages, result):
                with engine._lock:
                    engine._llm = replacement
                    engine._llm_checked = 12345
                raise LLMError('old client failed')
        old = Client(); engine._llm = old
        with patch.object(engine, 'llm', return_value=old), patch.object(engine, 'retrieve', return_value=[]):
            list(engine.answer('Question'))
        self.assertIs(engine._llm, replacement)
        self.assertEqual(engine._llm_checked, 12345)

    def test_deadline_limits_wait_for_catalog_lock(self):
        client = KiwixClient('http://local'); diagnostics = []
        with client._catalog_lock, patch('app.kiwix.get_text') as fetch:
            self.assertEqual(client.books(deadline=time.monotonic(), diagnostics=diagnostics), [])
        self.assertEqual(diagnostics[0]['failure_status'], 'timeout')
        fetch.assert_not_called()

    def test_old_search_cannot_update_replacement_archive_identity(self):
        client = KiwixClient('http://local')
        old = XML.replace('<name>', '<id>urn:uuid:old</id><name>')
        new = XML.replace('<name>', '<id>urn:uuid:new</id><name>')
        with patch('app.kiwix.get_text', side_effect=[old, new, '<rss/>']):
            snapshot = client.books()[0]
            client.invalidate_catalog()
            self.assertEqual(client.books()[0]['archive_uuid'], 'new')
            client.search_book(snapshot, 'question')
            self.assertIsNone(client.books()[0]['served_name'])

    def test_current_generation_failure_marks_client_for_recheck(self):
        engine = Engine({'kiwix_enabled':False})
        class Client:
            def options(self): return dict(context=10000, max_tokens=100, context_margin=100)
            def count_prompt(self, messages): return 10
            def describe(self): return {'backend':'test'}
            def stream_chat(self, messages, result): raise LLMError('failed')
        client = Client(); engine._llm = client; engine._llm_checked = 12345
        with patch.object(engine, 'llm', return_value=client), patch.object(engine, 'retrieve', return_value=[]):
            list(engine.answer('Question'))
        self.assertEqual(engine._llm_checked, 0)
