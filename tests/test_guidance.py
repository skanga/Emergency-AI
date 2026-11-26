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

    def test_burn_fallback_covers_protection_warmth_and_ice(self):
        for lang, required in (
                ('en', ('ice', 'rest of the person warm', 'loosely', 'not wrap', 'face')),
                ('pt', ('gelo', 'resto do corpo aquecido', 'solto', 'não enrole', 'rosto')),
                ('es', ('hielo', 'resto del cuerpo caliente', 'suelto', 'no envuelva', 'cara'))):
            with self.subTest(lang=lang):
                source = self.sources('Thermal burn on my arm. Should I use ice or butter?', lang)[0]
                for phrase in required:
                    self.assertIn(phrase, source['text'])

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
                                              [source], {
                                                  'diabetes': 'hypoglycemia', 'fire': 'cooking fire',
                                                  'flood': 'flood car', 'water_chemical': 'well water smells of gasoline',
                                                  'water_disinfection': 'bleach drinking water',
                                                  'carbon_monoxide': 'generator in garage headache',
                                                  'food_safety': 'power outage refrigerator milk',
                                                  'choking': '8-month-old choking',
                                              }.get(unit['topic'], unit['topic']), lang)
                    self.assertEqual(meta['status'], 'passed', meta['issues'])

    def test_refined_actionable_units_in_each_language(self):
        expected = {
            'adult unresponsive only gasping CPR': ('adult-cpr-compressions', 'adult-cpr-continuation'),
            '8-month-old choking awake cannot breathe': ('infant-choking-responsive', 'infant-choking-unresponsive'),
            'stroke drooping face slurred speech': ('stroke-response',),
            'child swallowed drain cleaner': ('poison-swallowed',),
            'generator in garage headache nausea': ('carbon-monoxide-escape',),
            'severe bleeding from leg despite pressure': ('bleeding-tourniquet',),
        }
        for question, ids in expected.items():
            for lang in ('en', 'pt', 'es'):
                with self.subTest(question=question, lang=lang):
                    found = {s['guidance_unit'] for s in self.sources(question, lang)}
                    self.assertTrue(set(ids) <= found, found)

    def test_infant_and_adult_procedures_remain_separate(self):
        unresponsive = self.sources('8-month-old choking unconscious not breathing')
        ids = {s['guidance_unit'] for s in unresponsive}
        self.assertIn('infant-choking-unresponsive', ids)
        self.assertNotIn('infant-choking-responsive', ids)
        self.assertNotIn('adult-cpr-compressions', ids)
        self.assertNotIn('adult-cpr-continuation', ids)
        for question in ('adult choking', 'newborn not breathing', '8-month-old awake breathing normally CPR'):
            self.assertNotIn('adult-cpr-compressions',
                             {s['guidance_unit'] for s in self.sources(question)})

    def test_captured_questions_survive_runtime_fallback(self):
        from app.engine import Engine
        cases = json.loads((Path(__file__).parent / 'evals/emergency_advice/cases.json').read_text())['cases']
        target_ids = {'cpr', 'infant_choking', 'bleeding', 'stroke', 'poison', 'co',
                      'water_chemical', 'chemical_water', 'cpr_not_indicated', 'bleeding_lay_iv', 'allergy_negated', 'food'}
        for case in cases:
            if case['id'] not in target_ids:
                continue
            request = case['request']
            for lang in ('en', 'pt', 'es'):
                with self.subTest(case=case['id'], lang=lang):
                    sources = [dict(source, n=i+1) for i,source in enumerate(
                        self.sources(request['q'], lang, request['history']))]
                    text, _, meta = Engine._fallback(sources, lang, [], request['q'], request['history'])
                    self.assertTrue(text, meta)
                    self.assertEqual(meta['status'], 'composed', meta)
        question = 'Our well water smells of gasoline after the flood. Can boiling or bleach make it safe?'
        for lang in ('en', 'pt', 'es'):
            sources = [dict(source, n=i+1) for i,source in enumerate(self.sources(question, lang))]
            text, _, meta = Engine._fallback(sources, lang, [], question, [])
            self.assertTrue(text, meta)

    def test_development_routing_misses_survive_runtime_fallback(self):
        from app.engine import Engine
        cases = json.loads((Path(__file__).parent / 'evals/emergency_advice/development-cases.json').read_text())['cases']
        expected = {'fire_extinguisher': 'cooking-fire',
                    'hypo_unsafe_swallow': 'hypoglycemia-unresponsive', 'burn_es': 'burn-cooling'}
        for case in cases:
            if case['id'] not in expected:
                continue
            request = case['request']
            with self.subTest(case=case['id']):
                sources = [dict(source, n=i+1) for i, source in enumerate(
                    self.sources(request['q'], request['lang']))]
                units = {source['guidance_unit'] for source in sources}
                self.assertIn(expected[case['id']], units)
                if case['id'] == 'hypo_unsafe_swallow':
                    self.assertNotIn('hypoglycemia-oral', units)
                text, _, meta = Engine._fallback(sources, request['lang'], [], request['q'], [])
                self.assertTrue(text, meta)
                self.assertEqual(meta['status'], 'composed', meta)
                if case['id'] == 'hypo_unsafe_swallow':
                    self.assertIn('unable to swallow safely, seek emergency help', text)
                    self.assertNotIn('15 grams', text)

    def test_actionable_steps_and_complete_conditions(self):
        from app.guidance import load_catalog
        units = {u['id']:u for u in load_catalog()}
        conditions = {
            'adult-cpr-compressions': ('100', '120', '5', '6', 'center', 'firm'),
            'adult-cpr-continuation': ('30', '2', 'trained', 'exhausted'),
            'infant-choking-responsive': ('5', 'lower', 'back blows', 'chest thrusts'),
            'infant-choking-unresponsive': ('30', '2', '4 cm', 'visible'),
            'bleeding-tourniquet': ('5', '7.5', 'joint', 'stops', 'not loosen'),
            'stroke-response': ('time', 'not wait'),
            'poison-swallowed': ('vomiting', 'vinegar', 'product'),
            'carbon-monoxide-escape': ('fresh air', 'garage', 'not re-enter'),
        }
        for unit_id, required in conditions.items():
            self.assertIn(unit_id, units)
            text = units[unit_id]['translations']['en']
            for phrase in required:
                self.assertIn(phrase, text)

    def test_anaphylaxis_posture_has_its_own_condition(self):
        from app.guidance import load_catalog
        unit = next(u for u in load_catalog() if u['id']=='anaphylaxis-injector')
        for lang, phrase in (('en','If anaphylaxis is suspected, lie down'),
                             ('pt','Se houver suspeita de anafilaxia, deite'),
                             ('es','Si sospecha anafilaxia, acuéstese')):
            self.assertIn(phrase, unit['translations'][lang])

    def test_asymptomatic_allergy_keeps_prescribed_plan(self):
        sources = self.sources('No swelling or breathing trouble after peanuts. Should I use epinephrine?')
        self.assertIn('allergy-action-plan', {s['guidance_unit'] for s in sources})

    def test_infant_unresponsive_transition_survives_runtime(self):
        from app.engine import Engine
        history = [{'role':'user','content':'My 8-month-old is choking and cannot cry.'}]
        for lang, question in (('en','Now unconscious and not breathing. CPR?'),
                               ('pt','Agora inconsciente e não respira. RCP?'),
                               ('es','Ahora inconsciente y no respira. RCP?')):
            with self.subTest(lang=lang):
                sources = [dict(source, n=i+1) for i,source in enumerate(self.sources(question, lang, history))]
                text, _, meta = Engine._fallback(sources, lang, [], question, history)
                self.assertTrue(text, meta)
                self.assertNotIn('5–6 cm', text)
                self.assertNotIn('5 back blows', text)
                self.assertIn('4 cm', text)

    def test_food_outage_and_lay_iv_have_actionable_boundaries(self):
        for lang, discard, refusal in (('en','4 hours','do not insert an IV'),
                                       ('pt','4 horas','não insira um acesso IV'),
                                       ('es','4 horas','no inserte una vía IV')):
            food = self.sources('power outage refrigerator milk', lang)
            self.assertTrue(food)
            self.assertIn(discard, ' '.join(s['text'] for s in food))
            bleeding = self.sources('severe bleeding no medical training IV kit', lang)
            self.assertIn(refusal, ' '.join(s['text'] for s in bleeding))

    def test_infant_ratio_retains_single_rescuer_condition(self):
        from app.guidance import load_catalog
        unit = next(u for u in load_catalog() if u['id']=='infant-choking-unresponsive')
        for lang, phrase in (('en','For a single rescuer'), ('pt','Para um único socorrista'),
                             ('es','Para un solo rescatista')):
            self.assertIn(phrase, unit['translations'][lang])

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
