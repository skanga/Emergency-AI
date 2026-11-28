"""Regression cases from the full-main evaluation, with unsafe near-matches."""
import json
from pathlib import Path
import re
import unittest

from app.answer_validation import validate_answer
from app.guidance import guidance_sources, fallback_answer
from app.query_planner import plan_query

FIXTURE = Path(__file__).parent / 'fixtures/retrieval/full-main-condition-cases.json'


class QualityConditionTests(unittest.TestCase):
    def validate(self, answer, source, question, lang='en', history=None):
        sources = source if isinstance(source, list) else [dict(n=1, id='test', text=source)]
        return validate_answer(answer, sources, question, lang, history)

    def test_captured_released_failures_are_blocked(self):
        for case in json.loads(FIXTURE.read_text()):
            if case['expected'] != 'blocked':
                continue
            with self.subTest(case=case['key']):
                rendered, report = self.validate(case['draft'], case['sources'],
                    case['request']['q'], case['request']['lang'], case['request']['history'])
                self.assertFalse(rendered)
                self.assertIn(case['issue'], report['issues'])

    def test_captured_qualified_drafts_are_released(self):
        for case in json.loads(FIXTURE.read_text()):
            if case['expected'] != 'passed':
                continue
            with self.subTest(case=case['key']):
                rendered, report = self.validate(case['draft'], case['sources'],
                    case['request']['q'], case['request']['lang'], case['request']['history'])
                self.assertTrue(rendered, report['issues'])

    def test_heat_shutdown_requires_own_safe_approach(self):
        for lang, q, good, bad in (
            ('en', 'A pan of oil is on fire', 'Only if safe, turn off the heat', 'Turn off the heat immediately'),
            ('pt', 'Fogo na panela com óleo', 'Somente se for seguro, desligue o fogo', 'Desligue o fogo imediatamente'),
            ('es', 'Fuego en una sartén con aceite', 'Solo si es seguro, apague el calor', 'Apague el calor inmediatamente')):
            with self.subTest(lang=lang):
                self.assertTrue(self.validate(good+' [S1].', good, q, lang)[0])
                self.assertIn('fire_approach_condition_missing', self.validate(bad+' [S1].', good, q, lang)[1]['issues'])
                self.assertFalse(self.validate(bad+' [S1]. '+good+' [S1].', good, q, lang)[0])

    def test_flood_trapped_and_current_prerequisites(self):
        good = 'If the vehicle is trapped in fast-moving water, stay inside unless water rises inside; then seek refuge on the roof'
        for bad in (good.replace('trapped in fast-moving', 'already in'),
                    good.replace('fast-moving ', ''),
                    good.replace('trapped in', 'not trapped in'),
                    good.replace('rises inside', 'rises significantly inside')):
            with self.subTest(bad=bad):
                self.assertIn('flood_entrapment_condition_missing', self.validate(bad+' [S1].', good, 'Floodwater road SUV')[1]['issues'])
        self.assertTrue(self.validate(good+' [S1].', good, 'Floodwater road SUV')[0])

    def test_repeat_injector_timing_uses_cited_source(self):
        good = 'If symptoms persist 5 minutes after the first injection, use a second auto-injector if available'
        for wording in ('5–15', '1–5', '5 to 15'):
            with self.subTest(wording=wording):
                bad=good.replace('5 minutes', wording+' minutes')
                self.assertFalse(self.validate(bad+' [S1].', good, 'Anaphylaxis second injector')[0])
        self.assertTrue(self.validate(good+' [S1].', good, 'Anaphylaxis second injector')[0])
        sources=[dict(n=1,id='five',text=good),dict(n=2,id='range',text=good.replace('5 minutes','5–15 minutes'))]
        self.assertFalse(self.validate(good.replace('5 minutes','5–15 minutes')+' [S1].',sources,'Anaphylaxis second injector')[0])

    def test_list_conditions_cannot_be_alternatives_or_cross_heading(self):
        source='If unresponsive and not breathing normally, begin CPR'
        for prefix in ('If he becomes:\n* Unresponsive, OR\n* Not breathing normally\n',
                       'If he becomes:\n* Unresponsive, AND\n* Not breathing normally\n\n## Different situation\n'):
            self.assertFalse(self.validate(prefix+'Then begin CPR [S1].',source,'He is awake and breathing normally. CPR?')[0])

    def test_wrong_quantity_and_swallow_conditions_still_block(self):
        source='If awake and able to swallow safely, give 1/2 cup (~120 mL) of juice'
        for bad in (source.replace('120','1200'), source.replace('and','or'), source.replace('able to','unable to')):
            self.assertFalse(self.validate(bad+' [S1].',source,'Low blood sugar, unknown state')[0])

    def test_relaxed_citation_links_keep_action_conditions(self):
        cases={c['key']:c for c in json.loads(FIXTURE.read_text())}
        for key,old,new in (
            ('burn#2','only if they are not stuck to the skin','even if they are stuck to the skin'),
            ('hypo_alert#2','120 mL','1200 mL'),
            ('cpr_not_indicated#3','**AND**','**OR**')):
            c=cases[key]
            with self.subTest(key=key):
                self.assertIn(old,c['draft'])
                self.assertFalse(self.validate(c['draft'].replace(old,new),c['sources'],c['request']['q'])[0])

    def test_food_menu_requires_safe_swallowing_evidence(self):
        case=next(c for c in json.loads(FIXTURE.read_text()) if c['key']=='hypo_alert#2')
        sources=[dict(s,text=s['text'].replace('must be conscious and able to swallow','may be unconscious and unable to swallow')) for s in case['sources']]
        self.assertFalse(self.validate(case['draft'],sources,case['request']['q'])[0])

    def test_repeat_dose_paraphrases_keep_interval(self):
        source='If symptoms persist 5 minutes after the first injection, use a second auto-injector if available'
        for action in ('use the second injector', 'administer another injection', 'give a second dose', 'repeat the epinephrine injection'):
            with self.subTest(action=action):
                self.assertFalse(self.validate('If symptoms persist 5–15 minutes after the first injection, '+action+' [S1].',source,'Anaphylaxis symptoms persist')[0])

    def test_citation_linking_does_not_release_known_snake_cleaning_gap(self):
        question='A snake bit my ankle; unknown species and region'
        source='In the United States, wash the bite with soap and water'
        self.assertFalse(self.validate('Wash the bite. Soap and water are available [S1].',source,question)[0])

    def test_second_injector_cannot_borrow_initial_dose_or_skip_wait(self):
        first='If anaphylaxis is suspected, use an available adrenaline auto-injector following its instructions'
        repeat='If symptoms persist 5 minutes after the first injection, use a second auto-injector if available'
        question='My child has anaphylaxis. I used the first injector one minute ago. She is still wheezing.'
        for source in (first,first+'. '+repeat):
            self.assertFalse(self.validate('Use the second epinephrine auto-injector immediately [S1].',source,question)[0])
        self.assertTrue(self.validate('Use the second epinephrine auto-injector immediately [S1].',repeat,question.replace('one minute','6 minutes'))[0])

    def test_seizure_fallback_is_available_and_validated(self):
        for lang,q,terms in (
            ('en','My sister has a seizure for six minutes. Hold her down or put a spoon in her mouth?',('5 minutes','mouth','head')),
            ('pt','Minha irmã está com convulsão há seis minutos. Devo segurá-la?',('5 minutos','boca','cabeça')),
            ('es','Mi hermana tiene convulsiones desde hace seis minutos. ¿La sujeto?',('5 minutos','boca','cabeza'))):
            with self.subTest(lang=lang):
                sources=[dict(s,n=i+1) for i,s in enumerate(guidance_sources(plan_query(q,lang),lang))]
                answer,meta=fallback_answer(sources,lang,[])
                self.assertEqual(meta['status'],'composed')
                for term in terms:self.assertIn(term,answer)
                draft=re.sub(r'\[(\d+)\]',r'[S\1]',answer)
                self.assertTrue(self.validate(draft,sources,q,lang)[0])
