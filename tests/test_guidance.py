"""Acceptance tests for bounded, source-backed fallback evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from app.query_planner import plan_query


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.guidance'),
                             'The source-backed guidance catalog is not implemented')
        from app import guidance
        self.g = guidance

    def sources(self, question, lang='en', history=()):
        return self.g.guidance_sources(plan_query(question, lang, history), lang)

    def test_every_gap_in_every_language(self):
        questions = ['low blood sugar awake', 'low blood sugar unconscious',
                     'CPR awake breathing normally', 'severe bleeding IV',
                     'bleach water disinfection', 'chemical contaminated water',
                     'burn', 'anaphylaxis', 'snakebite', 'flood', 'heatstroke',
                     'cooking fire']
        for lang in ('en', 'pt', 'es'):
            for question in questions:
                with self.subTest(lang=lang, question=question):
                    sources = self.sources(question, lang)
                    self.assertTrue(sources)
                    for source in sources:
                        self.assertEqual(source['language'], lang)
                        self.assertEqual(source['kind'], 'guidance')
                        self.assertTrue(source['url'].startswith('https://'))
                        self.assertEqual(len(source['guidance_hash']), 64)
                        self.assertNotIn('n', source)
                    numbered = [dict(s, n=i+1) for i,s in enumerate(sources)]
                    answer, meta = self.g.fallback_answer(numbered, lang, [])
                    self.assertIn('[1]', answer)
                    self.assertEqual(meta['status'], 'composed')
                    self.assertNotIn('verified', meta)

    def test_history_and_topic_reset(self):
        history = [{'role':'user','content':'low blood sugar unconscious'},
                   {'role':'assistant','content':'Now awake and swallowing'}]
        ids = [s['guidance_unit'] for s in self.sources('What should I do now?', history=history)]
        self.assertIn('hypoglycemia-unresponsive', ids)
        self.assertNotIn('hypoglycemia-oral', ids)
        reset = self.sources('Different problem: cooking fire', history=history)
        self.assertTrue(reset)
        self.assertTrue(all(s['topic'] == 'fire' for s in reset))

    def test_negative_and_hypothetical_facts_retain_conditions(self):
        for question in ('low blood sugar but not unconscious',
                         'low blood sugar, what if he becomes unconscious?',
                         'hypoglycemia but cannot swallow'):
            for s in self.sources(question):
                self.assertTrue(s['text'].startswith(('If ', 'For ')))
        self.assertEqual(self.sources('There is no burn'), [])
        self.assertEqual(self.sources('How to burn an ISO disc?'), [])

    def test_translated_inputs_and_preserved_conditions(self):
        for lang, low, fire in (
            ('en', 'low blood sugar awake', 'cooking fire'),
            ('pt', 'glicose baixa consciente', 'fogo na cozinha'),
            ('es', 'glucosa baja consciente', 'fuego en la cocina')):
            self.assertEqual(self.sources(low, lang)[0]['guidance_unit'], 'hypoglycemia-oral')
            self.assertEqual(self.sources(fire, lang)[0]['topic'], 'fire')
            unconscious = self.sources('hipoglicemia inconsciente', lang)
            self.assertEqual([s['guidance_unit'] for s in unconscious],
                             ['hypoglycemia-unresponsive'])
        for question in ('a low sugar cake recipe', 'sugar for cooking',
                         'açúcar para bolo', 'azúcar para un pastel'):
            self.assertEqual(self.sources(question), [])
        self.assertEqual(self.sources('burn', 'fr'), [])

    def test_flood_vehicle_branch_keeps_rising_inside_condition(self):
        for lang, condition in (('en', 'rises inside'), ('pt', 'subir dentro'),
                                ('es', 'sube dentro')):
            answer, _ = self.g.fallback_answer(
                [dict(s, n=i+1) for i,s in enumerate(self.sources('flood car', lang))],
                lang, [])
            self.assertIn(condition, answer)

    def test_complete_units_pass_shared_applicability(self):
        from app.applicability import inapplicability_reason
        for lang in ('en', 'pt', 'es'):
            plan = plan_query('diabetic unconscious', lang)
            sources = self.sources(plan.question, lang)
            self.assertTrue(sources)
            for source in sources:
                self.assertIsNone(inapplicability_reason(source, plan))

    def test_catalog_composition_passes_answer_validation(self):
        from app.answer_validation import validate_answer
        from app.guidance import load_catalog, _source
        for unit in load_catalog():
            for lang in ('en', 'pt', 'es'):
                with self.subTest(unit=unit['id'], lang=lang):
                    source = dict(_source(unit, lang), n=1)
                    answer, _ = self.g.fallback_answer([source], lang, [])
                    _, meta = validate_answer(answer.replace('[1]', '[S1]'),
                                              [source], {'diabetes': 'hypoglycemia', 'fire': 'cooking fire',
                                                         'flood': 'flood car'}.get(unit['topic'], unit['topic']), lang)
                    self.assertEqual(meta['status'], 'passed', meta['issues'])

    def test_catalog_integrity_fails_closed(self):
        data = json.loads(self.g.CATALOG_PATH.read_text())
        data['units'][0]['translations']['en'] += ' Unsafe alteration.'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guidance.json'
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                self.g.load_catalog(path)

    def test_non_object_catalog_fails_with_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guidance.json'
            for value in ([], None, 'not a catalog', 3):
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.g.load_catalog(path)

    def test_flood_building_guidance_preserves_attic_exception(self):
        for lang, attic in (('en','enclosed attic'), ('pt','sótão fechado'), ('es','ático cerrado')):
            answer, _ = self.g.fallback_answer(
                [dict(s, n=i+1) for i,s in enumerate(self.sources('flood trapped in attic', lang))], lang, [])
            self.assertIn(attic, answer)

    def test_arbitrary_or_mutated_source_cannot_claim_guidance(self):
        source = dict(self.sources('burn')[0], n=1)
        for changes in ({'text':'Apply butter.'}, {'id':'forged'}, {'guidance_hash':'0'*64},
                        {'url':'https://example.com/spoof'}, {'language':'es'}):
            candidate = dict(source, **changes)
            answer, meta = self.g.fallback_answer([candidate], 'en', [])
            self.assertEqual(answer, '')
            self.assertEqual(meta['status'], 'unavailable')

    def test_conflicts_policy_errors_and_missing_evidence(self):
        burn = dict(self.sources('burn')[0], n=1)
        water = dict(self.sources('chemical contaminated water')[0], n=2)
        cases = [({'resolution':'policy_error'}, False),
                 ({'resolution':'unresolved','topic':'burn','source_ids':['other']}, True),
                 ({'resolution':'reviewed_precedence','source_ids':[burn['id'],'other'],
                   'preferred_source':'other'}, True)]
        for conflict, keeps_water in cases:
            answer, meta = self.g.fallback_answer([burn, water], 'en', [conflict])
            self.assertNotIn('[1]', answer)
            self.assertEqual('[2]' in answer, keeps_water)
        self.assertEqual(self.g.fallback_answer([], 'en', [])[0], '')

    def test_actual_engine_omission_and_policy_error_shapes(self):
        source = dict(self.sources('burn')[0], n=1)
        omitted = dict(source, context_omitted=True, original_text=source['text'],
                       text='READ_FULL_SOURCE')
        answer, meta = self.g.fallback_answer([omitted], 'en', [])
        self.assertIn('[1]', answer)
        self.assertEqual(meta['fallback_evidence_ids'], [source['id']])
        self.assertEqual(self.g.fallback_answer(
            [dict(omitted, original_text='Apply butter')], 'en', [])[0], '')
        policy_error = {'detection_basis':'policy_error', 'resolution':'unresolved',
                        'topic':'policy', 'source_ids':[]}
        self.assertEqual(self.g.fallback_answer([source], 'en', [policy_error])[0], '')

    def test_omitted_fallback_evidence_is_explicit(self):
        source = dict(self.sources('burn')[0], n=3, context_included=False)
        answer, meta = self.g.fallback_answer([source], 'en', [])
        self.assertIn('[3]', answer)
        self.assertEqual(meta['fallback_evidence_ids'], [source['id']])


if __name__ == '__main__':
    unittest.main()
