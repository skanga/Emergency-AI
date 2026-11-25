"""Evidence admission regressions from the November advice review."""
import json
from pathlib import Path
import unittest

from app.query_planner import plan_query
from app.retrieval import relevance

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/advice_applicability.json').read_text())


def source(text, title='First aid', section='Management', kind='kiwix'):
    return dict(text=text, title=title, doc_title=title, section=section, kind=kind)


class AdviceApplicabilityTests(unittest.TestCase):
    def test_captured_clinical_and_mixed_population_procedures_are_not_advice(self):
        for name, case in FIXTURES.items():
            req = case['request']
            plan = plan_query(req['q'], req['lang'], req['history'])
            for item in case['sources']:
                with self.subTest(case=name, section=item['section']):
                    self.assertEqual(relevance(item, plan), 0)

    def test_generic_headings_and_first_aid_words_do_not_license_clinical_steps(self):
        cases = [
            ('My father is unresponsive and gasping', 'Cardiac arrest', 'Start CPR. After 20 minutes in asystole, stop CPR and pronounce death.'),
            ('My father is unresponsive and gasping', 'Cardiac arrest', 'Call emergency services. If pregnant, displace the uterus; perform a Caesarean section.'),
            ('My husband is unconscious after insulin', 'Hypoglycemia', 'Call for help. Give D50 50 mL IV bolus.'),
            ('My husband is unconscious after insulin', 'Hypoglycemia', 'Call for help. Administer dextrose intravenously.'),
            ('My child has anaphylaxis and an auto-injector', 'Anaphylaxis', 'Use an auto-injector. If ineffective, intravenous glucagon can be administered.'),
            ('Meu marido está inconsciente após insulina', 'Hipoglicemia', 'Chame ajuda. Administre glicose por via intravenosa.'),
            ('Mi marido está inconsciente después de insulina', 'Hipoglucemia', 'Llame a emergencias. Administre glucosa por vía intravenosa.'),
        ]
        for question, title, body in cases:
            for kind in ('kiwix', 'kit'):
                with self.subTest(body=body, kind=kind):
                    self.assertEqual(relevance(source(body, title=title, kind=kind), plan_query(question)), 0)

    def test_warnings_about_clinical_treatment_do_not_hide_lay_first_aid(self):
        cases = [
            ('Anaphylaxis with a prescribed auto-injector', 'Anaphylaxis', 'Use the prescribed epinephrine auto-injector. Intravenous dosing requires specialist monitoring.'),
            ('Anaphylaxis with a prescribed auto-injector', 'Anaphylaxis', 'Use the prescribed auto-injector. Do not inject epinephrine intravenously.'),
            ('My father is unresponsive and gasping', 'Cardiac arrest', 'Start CPR and call for help. Do not stop CPR after an arbitrary time limit.'),
            ('My husband is unconscious after insulin', 'Hypoglycemia', 'Call emergency services. Do not give glucose by mouth to an unconscious person.'),
        ]
        for question, title, body in cases:
            with self.subTest(body=body):
                self.assertGreater(relevance(source(body, title=title), plan_query(question)), 0)

    def test_conscious_oral_treatment_body_is_not_for_unconscious_patient(self):
        body = 'For hypoglycemia, if awake and able to swallow, give 15 grams of oral glucose and wait 15 minutes.'
        self.assertEqual(relevance(source(body, title='Hypoglycemia'), plan_query('My husband is unconscious after insulin')), 0)
        self.assertGreater(relevance(source(body, title='Hypoglycemia'), plan_query('Low blood sugar; he is awake and can swallow')), 0)

    def test_infant_keeps_own_procedure_but_not_mixed_adult_instructions(self):
        plan = plan_query('My 8-month-old is unconscious and not breathing')
        good = 'For an unresponsive infant, call emergency services and start CPR. Alternate compressions and rescue breaths.'
        self.assertGreater(relevance(source(good, title='Infant CPR', section='First aid'), plan), 0)
        mixed = '**Adult:** If not trained, give continuous compressions only. **Infant:** Rescue breaths are especially important.'
        self.assertEqual(relevance(source(mixed, title='CPR'), plan), 0)

    def test_search_hits_without_body_can_still_be_fetched(self):
        hit = dict(title='Cardiac arrest', doc_title='Encyclopedia', section='')
        self.assertGreater(relevance(hit, plan_query('My father is unresponsive and gasping')), 0)

    def test_passive_resuscitation_termination_and_semicolon_steps_are_rejected(self):
        plan = plan_query('My father is unresponsive and gasping')
        for body in ('CPR can be stopped after 20 minutes without return of circulation.',
                     'Do not delay CPR; administer 1 mg epinephrine IV.',
                     'Never stop CPR. However, give 1 mg epinephrine IV.',
                     'If no pulse, administer 1 mg epinephrine IV.',
                     'No response to treatment: administer 1 mg epinephrine IV.',
                     'Do not delay CPR and administer 1 mg epinephrine IV.'):
            with self.subTest(body=body):
                self.assertEqual(relevance(source(body, title='Cardiac arrest'), plan), 0)

    def test_conditional_oral_prohibition_remains_available(self):
        body = 'For hypoglycemia call for help. If the person is unconscious, do not give glucose by mouth.'
        self.assertGreater(relevance(source(body, title='Hypoglycemia'), plan_query('My husband is unconscious after insulin')), 0)

    def test_alternative_clinical_passages_are_also_rejected(self):
        plan = plan_query('My father is unresponsive and gasping')
        for body in ('Emergency thoracotomy and bilateral thoracostomy.',
                     'Give typical adult ACLS drugs/dosages.',
                     'Administer activated charcoal within 1 hr of ingestion.',
                     'Administer octreotide: 50-100 mcg subcutaneous in adults.',
                     'Glucagon 5mg IM while obtaining access.',
                     '50mL D50W bolus. Start a D10 drip (100mL/hr).'):
            self.assertEqual(relevance(source(body, title='Cardiac arrest'), plan), 0)
