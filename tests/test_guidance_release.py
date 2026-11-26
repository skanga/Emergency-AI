"""Fallbacks are independent of rejected drafts and retain evidence identity."""
import unittest
from unittest.mock import Mock, patch

from app.engine import Engine


QUESTION = 'My husband is unconscious after taking insulin. Should I give him juice?'


class GuidanceReleaseTests(unittest.TestCase):
    def events(self, draft='UNRELEASED [S999].', ending='stop', model=True, **kw):
        engine = Engine({'kiwix_enabled':False})
        llm = Mock()
        llm.options.return_value = {'context':8192, 'max_tokens':2048, 'context_margin':256}
        llm.count_prompt.return_value = 100
        llm.describe.return_value = {'model':'fake'}
        def stream(messages, info):
            yield draft
            info.update(finish_reason=ending, incomplete=ending != 'stop')
        llm.stream_chat.side_effect = stream
        with patch.object(engine, 'llm', return_value=llm if model else None):
            return list(engine.answer(QUESTION, use_kiwix=False, **kw))

    def assert_fallback(self, events):
        text = ''.join(data for kind,data in events if kind == 'token')
        done = next(data for kind,data in events if kind == 'done')
        self.assertEqual(done['mode'], 'fallback', done)
        self.assertTrue(done['fallback']['used_source_ids'])
        self.assertNotIn('UNRELEASED', text)
        self.assertNotIn('UNRELEASED', str(done))
        self.assertRegex(text.lower(), r'(mouth|food|drink)')
        self.assertRegex(text, r'\[[1-9][0-9]*\]')
        return done

    def test_rejected_answer_produces_independent_help(self):
        done = self.assert_fallback(self.events())
        self.assertEqual(done['reason'], 'answer_validation_failed')
        self.assertEqual(done['generation']['validation']['status'], 'blocked')

    def test_incomplete_answer_produces_complete_fallback(self):
        done = self.assert_fallback(self.events(ending='length'))
        self.assertEqual(done['reason'], 'generation_failed')

    def test_model_unavailable_produces_useful_fallback(self):
        done = self.assert_fallback(self.events(model=False))
        self.assertEqual(done['reason'], 'model_unavailable')

    def test_unsafe_swallowing_still_gets_nonoral_help(self):
        engine = Engine({'kiwix_enabled':False})
        with patch.object(engine, 'llm', return_value=None):
            text, _, done = engine.answer_text('Low blood sugar. He is awake but cannot swallow.', use_kiwix=False)
        self.assertEqual(done['mode'], 'fallback', done)
        self.assertNotIn('give 15 grams', text)
        self.assertRegex(text.lower(), r'(help|emergency)')

    def test_deliberate_search_mode_is_not_automatic_advice(self):
        events = self.events(model=False, use_llm=False)
        done = next(data for kind,data in events if kind == 'done')
        self.assertEqual(done['mode'], 'search')
        self.assertFalse(done.get('fallback', {}).get('used_source_ids'))

    def test_policy_error_cannot_be_bypassed(self):
        with patch('app.engine.evaluate_conflicts', side_effect=ValueError('bad policy')):
            events = self.events()
        done = next(data for kind,data in events if kind == 'done')
        self.assertEqual(done['reason'], 'source_conflict')
        self.assertNotEqual(done['mode'], 'fallback')

    def test_omitted_guidance_is_labeled_before_its_citation(self):
        with patch.object(Engine, 'fit_messages') as fit:
            def omit(engine_llm, question, lang, sources, history):
                omitted = [dict(s, context_omitted=True, context_omitted_reason='token_budget',
                                text='Omitted', original_text=s.get('original_text', s['text'])) for s in sources]
                return [], omitted, {'included_source_ids':[], 'sources_omitted':[s['n'] for s in sources]}
            fit.side_effect = omit
            events = self.events()
        done = self.assert_fallback(events)
        self.assertFalse(done['sources_supplied'])
        sources = []
        for kind, data in events:
            if kind == 'sources':
                sources = data
            elif kind == 'token' and 'fallback' in data.lower():
                self.assertTrue(any(s.get('fallback_evidence') for s in sources))
        restored = [s for s in sources if s.get('fallback_evidence')]
        self.assertTrue(restored)
        self.assertTrue(all(s.get('model_context_omitted') for s in restored))
        self.assertEqual(done['generation']['included_source_ids'], [])
