"""Keep repeated catalog/capability work and context-fitting requests bounded."""
import json
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import document_index as docs
from app.engine import Engine
from app.llm import LLMError, OpenAICompatible


class HotPathTests(unittest.TestCase):
    def test_fts_capability_probe_is_shared(self):
        # Clear once introduced; the pre-fix implementation still demonstrates repeats.
        probe = getattr(docs, '_fts5_supported', None)
        if probe:
            probe.cache_clear()
            self.addCleanup(probe.cache_clear)
        with patch.object(docs.sqlite3, 'connect', wraps=sqlite3.connect) as connect:
            for _ in range(4):
                docs.DocumentIndex('/tmp/unused-index').supported()
        self.assertEqual(connect.call_count, 1)

    def test_catalog_cached_and_replacement_invalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'zims.json'
            path.write_text(json.dumps({'zims': [{'name': 'one', 'document_format': 'nautilus'}]}))
            index = Mock(); index.status.return_value = {'state': 'index_needed'}
            read_text = Path.read_text
            with patch.object(docs, 'ZIM_CONFIG_PATH', path, create=True), patch.object(Path, 'read_text', autospec=True, side_effect=read_text) as read:
                self.assertEqual(docs.document_state({'name': 'one'}, index)['state'], 'index_needed')
                docs.document_state({'name': 'one'}, index)
                self.assertEqual(read.call_count, 1)
                replacement = path.with_suffix('.new')
                replacement.write_text(json.dumps({'zims': [{'name': 'two', 'document_format': 'nautilus'}]}))
                replacement.replace(path)
                self.assertEqual(docs.document_state({'name': 'one'}, index)['state'], 'not_applicable')
                self.assertEqual(docs.document_state({'name': 'two'}, index)['state'], 'index_needed')
                self.assertEqual(read.call_count, 2)

    def source(self, n):
        return dict(n=n, id=str(n), kind='kit', doc_title='Guide', section='Steps', text='complete passage')

    def fit(self, size, allowed, history=()):
        engine = Engine({'kiwix_enabled': False})
        model = Mock()
        model.options.return_value = dict(context=1000, max_tokens=100, context_margin=100)
        def count(messages):
            # Complete source entries; all positive prefix counts are monotonic.
            sources = messages[-1]['content'].count('complete passage')
            return 800 if sources <= allowed and len(messages) == 2 else 900
        model.count_prompt.side_effect = count
        sources = [self.source(n) for n in range(1, size + 1)]
        result = engine.fit_messages(model, 'Question', 'en', sources, history)
        return result, model, sources

    def test_source_trimming_uses_logarithmic_counts(self):
        (messages, fitted, report), model, original = self.fit(32, 3)
        self.assertEqual(report['included_source_ids'], ['1', '2', '3'])
        self.assertLessEqual(model.count_prompt.call_count, 8)
        self.assertEqual(messages[-1]['content'].count('complete passage'), 3)
        self.assertTrue(all('context_omitted' not in s for s in original))
        self.assertTrue(all(s['original_text'] == 'complete passage' for s in fitted[3:]))

    def test_history_removed_before_evidence(self):
        (_, _, report), model, _ = self.fit(8, 8, [{'role':'user','content':'old'}, {'role':'assistant','content':'reply'}])
        self.assertTrue(report['history_omitted'])
        self.assertEqual(len(report['included_source_ids']), 8)
        self.assertEqual(model.count_prompt.call_count, 2)

    def test_empty_source_prompt_is_checked_separately(self):
        (_, _, report), model, _ = self.fit(8, 0)
        self.assertEqual(report['included_source_ids'], [])
        self.assertEqual(report['input_tokens'], 800)
        engine = Engine({}); model.count_prompt.return_value = 900; model.count_prompt.side_effect = None
        with self.assertRaises(LLMError):
            engine.fit_messages(model, 'Too long', 'en', [self.source(1)])

    def test_catalog_inplace_edit_and_parse_error_do_not_serve_stale_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'zims.json'
            index = Mock(); index.status.return_value = {'state': 'index_needed'}
            with patch.object(docs, 'ZIM_CONFIG_PATH', path):
                path.write_text('{"zims": [{"name":"one", "document_format":"nautilus"}]}')
                self.assertEqual(docs.document_state({'name':'one'}, index)['state'], 'index_needed')
                old = path.stat().st_mtime_ns
                path.write_text('{"zims": [{"name":"two", "document_format":"nautilus"}]}')
                os.utime(path, ns=(old + 1000000000, old + 1000000000))
                self.assertEqual(docs.document_state({'name':'one'}, index)['state'], 'not_applicable')
                path.write_text('broken')
                with self.assertRaises(json.JSONDecodeError):
                    docs.document_state({'name':'two'}, index)
                path.write_text('{"zims": []}')
                self.assertEqual(docs.document_state({'name':'two'}, index)['state'], 'not_applicable')

    def test_llama_http_requests_are_bounded_during_trimming(self):
        client = OpenAICompatible('http://localhost/v1', backend='llamacpp')
        engine = Engine({'kiwix_enabled':False})
        def reply(url, data, **kwargs):
            if url.endswith('/apply-template'):
                count = data['messages'][-1]['content'].count('complete passage')
                body = {'prompt': str(count)}
            else:
                self.assertTrue(url.endswith('/tokenize'))
                body = {'tokens': [1] * (800 if int(data['content']) <= 3 else 900)}
            return io.BytesIO(json.dumps(body).encode())
        with patch.object(client, 'options', return_value=dict(context=1000, max_tokens=100, context_margin=100, thinking=False)), patch('app.llm.open_url', side_effect=reply) as http:
            _, _, report = engine.fit_messages(client, 'Question', 'en', [self.source(n) for n in range(1, 33)])
        self.assertEqual(report['included_source_ids'], ['1','2','3'])
        self.assertLessEqual(http.call_count, 16)
        self.assertEqual(report['input_tokens'], 800)

    def test_previously_omitted_sources_keep_their_reason(self):
        engine = Engine({})
        model = Mock(); model.options.return_value = dict(context=1000, max_tokens=100, context_margin=100)
        model.count_prompt.side_effect = lambda messages: 800 if messages[-1]['content'].count('complete passage') <= 1 else 900
        excluded = dict(self.source(2), context_omitted=True, context_omitted_reason='conflict_unresolved')
        _, fitted, report = engine.fit_messages(model, 'Question', 'en', [self.source(1), excluded, self.source(3)])
        self.assertEqual(report['included_source_ids'], ['1'])
        self.assertEqual(fitted[1]['context_omitted_reason'], 'conflict_unresolved')
        self.assertEqual(fitted[2]['context_omitted_reason'], 'token_budget')
