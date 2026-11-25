"""Synthetic source disagreements must survive ranking and every answer mode."""
import unittest
from unittest.mock import patch, Mock

from app.engine import Engine
from app.source_policy import evaluate_conflicts


def source(key, text, kind='kit', score=1):
    return dict(id=key, text=text, kind=kind, retrieval_score=score,
                doc_title=key, section='Procedure', source_version=key + '-v1')


class ConflictContextTests(unittest.TestCase):
    def test_conflict_beyond_caps_and_tiny_context_blocks_all_answer_modes(self):
        local = [source('local', 'Add 2 ml of solution.')]
        library = [source('other', 'A separate passage.', 'kiwix', 100),
                   source('conflict', 'Add 4 ml of solution.', 'kiwix')]
        for use_llm in (False, True):
            engine = Engine({'context_chars': 1, 'kiwix_results': 1})
            with patch('app.retrieval.local_sources', return_value=local), \
                    patch('app.retrieval.library_sources', return_value=library), \
                    patch.object(engine, 'llm') as model:
                text, refs, info = engine.answer_text('synthetic', use_llm=use_llm)
            self.assertIn('unresolved', text.lower())
            self.assertNotIn('2 ml', text)
            self.assertNotIn('4 ml', text)
            model.assert_not_called()
            self.assertEqual(info['reason'], 'source_conflict')
            self.assertEqual(len(info['retrieval']['conflicts']), 1)
            self.assertEqual({s['id'] for s in refs}, {'local', 'other', 'conflict'})
            self.assertEqual(next(s for s in refs if s['id']=='conflict')['original_text'], library[1]['text'])

    def test_reviewed_precedence_excludes_old_passage_but_keeps_reference(self):
        local = source('local', 'Add 2 ml of solution.')
        library = source('library', 'Add 4 ml of solution.', 'kiwix')
        rule = dict(id='review', topic='synthetic', reviewer='Test', reviewed_at='2026-11-25',
                    rationale='Synthetic correction.', sources={'local':'local-v1', 'library':'library-v1'},
                    preferred_source='library')
        records = evaluate_conflicts([local, library], ['synthetic'], {}, {'rules':[rule]})
        engine = Engine({'kiwix_results': 0})
        with patch('app.retrieval.local_sources', return_value=[local]), \
                patch('app.retrieval.library_sources', return_value=[library]), \
                patch('app.engine.evaluate_conflicts', return_value=records, create=True):
            text, refs, info = engine.answer_text('synthetic', use_llm=False)
        self.assertNotIn('2 ml', text)
        self.assertIn('4 ml', text)
        self.assertIn('Synthetic correction.', text)
        self.assertIn('local-v1', text)
        self.assertEqual(local['text'], 'Add 2 ml of solution.')
        self.assertEqual(next(s for s in refs if s['id']=='local')['context_omitted_reason'], 'reviewed_precedence')

    def test_extractive_uses_included_sources_after_omitted_references(self):
        engine = Engine({})
        refs = [dict(source(str(i), 'hidden'), n=i, context_omitted=True) for i in range(1, 4)]
        refs.append(dict(source('safe', 'Whole usable passage.'), n=4))
        text = engine.extractive_answer('en', refs)
        self.assertIn('Whole usable passage.', text)
        self.assertNotIn('hidden', text)

    def test_failed_library_still_returns_local(self):
        engine = Engine({})
        with patch('app.retrieval.local_sources', return_value=[source('local','Complete local passage.')]), \
                patch('app.retrieval.library_sources', side_effect=OSError('offline')):
            text, refs, info = engine.answer_text('synthetic', use_llm=False)
        self.assertIn('Complete local passage.', text)
        self.assertEqual(info['retrieval']['status'], 'failed')

    def test_corrupt_policy_fails_closed_with_visible_notice(self):
        engine = Engine({})
        with patch('app.retrieval.local_sources', return_value=[source('local','Add 2 ml of solution.')]), \
                patch('app.engine.evaluate_conflicts', side_effect=ValueError('invalid_source_policy'), create=True):
            text, refs, info = engine.answer_text('synthetic', use_kiwix=False, use_llm=False)
        self.assertIn('policy', text.lower())
        self.assertNotIn('2 ml', text)
        self.assertEqual(info['reason'], 'source_conflict')

    def test_reviewed_preferred_passage_that_does_not_fit_cannot_use_general_knowledge(self):
        engine = Engine({'context_chars': 1})
        local = source('local', 'Add 2 ml of solution.')
        library = source('library', 'Add 4 ml of solution.', 'kiwix')
        record = dict(id='r', topic='synthetic', source_ids=['local','library'],
                      versions={'local':'local-v1','library':'library-v1'}, preferred_source='library',
                      resolution='reviewed_precedence', detection_basis='reviewed_rule', explanation='Correction.')
        with patch('app.retrieval.local_sources', return_value=[local]), \
                patch('app.retrieval.library_sources', return_value=[library]), \
                patch('app.engine.evaluate_conflicts', return_value=[record]), \
                patch.object(engine, 'llm') as model:
            model.return_value.options.return_value = {'context':4000,'max_tokens':1000,'context_margin':256}
            model.return_value.count_prompt.return_value = 10
            model.return_value.stream_chat.return_value = iter(['Add 2 ml of solution.'])
            text, refs, info = engine.answer_text('synthetic')
        model.return_value.stream_chat.assert_not_called()
        self.assertNotIn('2 ml', text)
        self.assertIn('not supplied', text)
        self.assertEqual(info['reason'], 'reviewed_source_omitted')

    def test_token_fitting_reports_actual_included_ids_and_keeps_original(self):
        engine = Engine({})
        model = Mock()
        model.options.return_value = {'context':100,'max_tokens':20,'context_margin':10}
        model.count_prompt.side_effect = lambda messages: 80 if 'SECOND' in str(messages) else 60
        refs = [dict(source('first','FIRST'),n=1), dict(source('second','SECOND'),n=2)]
        messages, fitted, report = engine.fit_messages(model, 'Question', 'en', refs)
        self.assertEqual(report['included_source_ids'], ['first'])
        self.assertEqual(fitted[1]['original_text'], 'SECOND')
        self.assertEqual(str(messages).count('FIRST'), 1)
        self.assertNotIn('SECOND', str(messages))
        self.assertLessEqual(report['input_tokens']+20+10,100)

    def test_retrieval_and_index_cleanup_preserve_local_and_personal_files(self):
        import hashlib
        from pathlib import Path
        import tempfile
        from app.knowledge import KnowledgeBase
        from app.document_index import DocumentIndex

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in {'en/guide.md':'# Synthetic guide\n\n## Procedure\nAdd 2 ml of synthetic solution.',
                               'extra/personal.txt':'Personal synthetic notes.\nKeep these bytes unchanged.',
                               'extra/private.bin':'Other personal content.'}.items():
                path = root / 'knowledge' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body.encode())
            def hashes():
                return {str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (root/'knowledge').rglob('*') if p.is_file()}
            before = hashes()
            engine = Engine({})
            engine.kb = KnowledgeBase(root/'knowledge')
            with patch('app.retrieval.library_sources', side_effect=OSError('offline')):
                text, refs, info = engine.answer_text('synthetic solution', use_llm=False)
            self.assertTrue(refs)
            self.assertIn('2 ml', text)
            DocumentIndex(root/'indexes').cleanup([])
            self.assertEqual(hashes(), before)

    def test_repeated_candidate_is_supplied_once(self):
        engine = Engine({})
        passage = source('same', 'Unique complete passage.', 'kiwix')
        with patch('app.retrieval.local_sources', return_value=[]), \
                patch('app.retrieval.library_sources', return_value=[passage, dict(passage)]):
            refs = engine.retrieve('synthetic', 'en')
        self.assertEqual(len(refs), 1)
        self.assertEqual(str(engine.build_messages('synthetic','en',refs)).count('Unique complete passage.'), 1)
