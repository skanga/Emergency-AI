import json
import unittest
from pathlib import Path

from app.query_planner import plan_query


class QueryPlannerTests(unittest.TestCase):
    def test_compression_question_routes_without_assuming_arrest(self):
        for question, lang in (
                ('He is awake and breathing normally. Should I start chest compressions?', 'en'),
                ('Ele está acordado. Devo iniciar compressões torácicas?', 'pt'),
                ('Está despierto. ¿Inicio compresiones torácicas?', 'es')):
            with self.subTest(lang=lang):
                plan = plan_query(question, lang)
                self.assertIn('cpr', plan.topics)
                self.assertEqual(plan.scope['consciousness'], 'responsive')

    def test_explicit_infant_age_boundary_is_not_one_year_old(self):
        from app.query_planner import _age, normalize
        for phrase in ('baby under 1 year', 'bebê menor de 1 ano',
                       'bebé menor de 1 año', 'infant younger than 1 year'):
            with self.subTest(phrase=phrase):
                self.assertEqual(_age(normalize(phrase)), 'infant')
        for phrase in ('1 year old', '1 ano', '1 año', 'child under 5 years',
                       'not under 1 year', 'não menor de 1 ano', 'no menor de 1 año'):
            with self.subTest(phrase=phrase):
                self.assertEqual(_age(normalize(phrase)), 'child')

    def test_later_infant_boundary_does_not_override_patient_age(self):
        for question, expected in (
                ('My child is 2 years old, not a baby under 1 year.', 'child'),
                ('He is 30 years old. Does the advice for babies under 1 year apply?', 'adult'),
                ('Meu filho tem 2 anos, não é um bebê menor de 1 ano.', 'child')):
            with self.subTest(question=question):
                self.assertEqual(plan_query(question).scope['age_group'], expected)

    def test_original_cases_have_bounded_multilingual_topics(self):
        cases = json.loads(Path('tests/fixtures/retrieval/cases.json').read_text())
        expected = ['anaphylaxis', 'anaphylaxis', 'bleeding', 'burn', 'carbon_monoxide', 'cpr', 'dehydration', 'diabetes', 'flood', 'food_safety', 'fire', 'heatstroke', 'choking', 'cpr', 'poison', 'carbon_monoxide', 'seizure', 'snakebite', 'cpr', 'stroke', 'water_disinfection', 'water_chemical', 'electrical']
        for case, topic in zip(cases, expected):
            req = case['request']
            with self.subTest(case=case['id']):
                plan = plan_query(req['q'], req['lang'], req['history'])
                self.assertIn(topic, plan.topics)
                self.assertEqual(set(plan.queries_by_language), {'en', 'es', 'pt'})
                self.assertTrue(all(1 <= len(q) <= 2 for q in plan.queries_by_language.values()))
        self.assertEqual(plan_query(**{'question': cases[13]['request']['q'], 'history': cases[13]['request']['history']}).scope['age_group'], 'infant')

    def test_whole_words_unknowns_and_nonmedical_context(self):
        for query in ('My camera is unresponsive', 'engine gasping', 'burnished copper', 'seizureproof camera'):
            plan = plan_query(query)
            self.assertEqual(plan.topics, ())
            self.assertTrue(plan.limited_cross_language)
            self.assertEqual(set(plan.queries_by_language), {'en'})

    def test_recent_user_history_and_override(self):
        history = [{'role': 'user', 'content': 'My infant is choking'}, {'role': 'assistant', 'content': 'stroke seizure'}]
        plan = plan_query('He is an adult, not choking. Now unconscious and not breathing.', history=history)
        self.assertEqual(plan.scope['age_group'], 'adult')
        self.assertIn('choking', plan.scope['negated_facts'])
        self.assertNotIn('choking', plan.topics)
        self.assertIn('cpr', plan.topics)
        reset = plan_query('New question: how do I repair my camera?', history=history)
        self.assertEqual(reset.context_terms, ())
        self.assertEqual(reset.topics, ())

    def test_multilingual_symptoms(self):
        for text, lang, topic in [('Não responde e está ofegante', 'pt', 'cpr'), ('Bebé atragantado no puede respirar', 'es', 'choking'), ('Língua inchada e chiado após amendoim', 'pt', 'anaphylaxis')]:
            self.assertIn(topic, plan_query(text, lang).topics)

    def test_source_language_codes_and_negated_age(self):
        from app.query_planner import normalize_language
        self.assertEqual(normalize_language('eng'), 'en')
        self.assertEqual(normalize_language('por'), 'pt')
        self.assertEqual(normalize_language('spa'), 'es')
        self.assertEqual(normalize_language('pt-BR'), 'pt')
        self.assertEqual(plan_query('not an infant, an adult choking').scope['age_group'], 'adult')
        self.assertEqual(plan_query('camera manual', 'eng').request_language, 'en')

    def test_numeric_ages_and_locales(self):
        for text, expected in [('A 64-year-old man collapsed', 'adult'), ('18 months old choking', 'child'), ('8 months old choking', 'infant'), ('bebê de 18 meses engasgado', 'child'), ('niño de 8 meses atragantado', 'infant'), ('adulto de 64 anos', 'adult')]:
            with self.subTest(text=text):
                self.assertEqual(plan_query(text).scope['age_group'], expected)

    def test_history_correction_persists(self):
        history = [{'role': 'user', 'content': 'My infant is choking'}, {'role': 'user', 'content': 'He is not choking anymore, but unresponsive and gasping'}]
        plan = plan_query('What should I do next?', history=history)
        self.assertIn('cpr', plan.topics)
        self.assertNotIn('choking', plan.topics)
        self.assertIn('choking', plan.scope['negated_facts'])
        self.assertEqual(plan.scope['age_group'], 'infant')

    def test_negative_unrelated_topic_does_not_reset_history(self):
        plan = plan_query('He is not bleeding. What should I do?', history=[{'role': 'user', 'content': 'My infant is choking'}])
        self.assertIn('choking', plan.topics)
        self.assertEqual(plan.scope['age_group'], 'infant')
        self.assertIn('bleeding', plan.scope['negated_facts'])

    def test_equipment_does_not_suppress_explicit_emergency(self):
        plan = plan_query('The engine is running in the garage and there is carbon monoxide')
        self.assertIn('carbon_monoxide', plan.topics)
        self.assertEqual(set(plan.queries_by_language), {'en', 'pt', 'es'})
        self.assertEqual(plan_query('How does a four stroke engine work?').topics, ())

    def test_consciousness_facts_negation_and_followups(self):
        for text, expected in [('infant choking and unconscious', 'unresponsive'), ('choking but not unconscious', 'responsive'), ('awake and choking', 'responsive'), ('choking, not responsive', 'unresponsive'), ('infant choking, cannot cry and turning blue', None)]:
            with self.subTest(text=text):
                self.assertEqual(plan_query(text).scope['consciousness'], expected)
        history = [{'role': 'user', 'content': 'My infant is choking and unresponsive'}]
        self.assertEqual(plan_query('What now?', history=history).scope['consciousness'], 'unresponsive')
        self.assertEqual(plan_query('He is awake now', history=history).scope['consciousness'], 'responsive')
        self.assertIsNone(plan_query('New question: repair camera', history=history).scope['consciousness'])


class PlannerRelevanceRegressions(unittest.TestCase):
    def test_observed_multilingual_paraphrases(self):
        cases = json.loads(Path('tests/manual/retrieval_manifest.json').read_text())['cases']
        expected = ['cpr'] * 3 + ['choking'] * 3 + ['anaphylaxis'] * 3 + ['stroke'] * 3 + ['carbon_monoxide'] * 3 + ['water_chemical'] * 3 + ['burn', 'heatstroke', 'seizure', 'choking', 'anaphylaxis', 'fire']
        for case, topic in zip(cases[:24], expected):
            with self.subTest(case=case['id']):
                plan = plan_query(case['q'], case['lang'], case.get('history', []))
                self.assertIn(topic, plan.topics)
                if topic == 'choking' and case['id'] in ('heldout-04', 'heldout-05', 'heldout-06'):
                    self.assertEqual(plan.scope['age_group'], 'infant')
        self.assertNotIn('choking', plan_query(cases[23]['q'], history=cases[23]['history']).topics)

    def test_nonemergency_meanings_do_not_route_to_emergency_topics(self):
        cases = json.loads(Path('tests/manual/retrieval_manifest.json').read_text())['cases']
        for case in [c for c in cases if c['split'] == 'negative']:
            with self.subTest(case=case['id']):
                self.assertEqual(plan_query(case['q'], case['lang']).topics, ())

    def test_explicit_topic_change_clears_all_patient_facts(self):
        history = [{'role': 'user', 'content': 'My infant is choking and unconscious'}]
        for text in ('Different problem: how can I preserve beans?', 'Outro problema: guardar feijão', 'Otro problema: conservar frijoles'):
            with self.subTest(text=text):
                plan = plan_query(text, history=history)
                self.assertEqual(plan.topics, ())
                self.assertIsNone(plan.scope['age_group'])
                self.assertIsNone(plan.scope['consciousness'])
                self.assertEqual(plan.context_terms, ())

    def test_nonmedical_objects_do_not_erase_explicit_emergencies(self):
        for question, topic in [
            ('My father has a stroke and slurred speech next to the engine', 'stroke'),
            ('My sister had a seizure while eating salad', 'seizure'),
            ('My baby is choking beside the camera', 'choking'),
        ]:
            with self.subTest(question=question):
                self.assertIn(topic, plan_query(question).topics)

    def test_configured_symptoms_override_nonmedical_sense(self):
        plan = plan_query('My father had a stroke while swimming; his smile is crooked and one arm is weak')
        self.assertIn('stroke', plan.topics)
