"""Generated instructions must pass checks before any answer text is released."""
import unittest
from unittest.mock import Mock, patch

from app.engine import Engine
from app.llm import LLMError


def source(n=1, text='If unresponsive and not breathing normally, start CPR.', **kw):
    return dict(n=n, id=f'passage-{n}', kind='kiwix', doc_title='Guide', section='First aid', text=text, **kw)


class AnswerReleaseTests(unittest.TestCase):
    def run_answer(self, answer, question='First aid question', sources=None, history=None, lang='en', ending='stop'):
        engine = Engine({})
        model = Mock()
        model.options.return_value = {'context':8192, 'max_tokens':2048, 'context_margin':256}
        model.count_prompt.return_value = 100
        model.describe.return_value = {'model':'fake'}
        def stream(messages, info):
            for piece in (answer[:len(answer)//2], answer[len(answer)//2:]):
                yield piece
            if ending == 'error':
                raise LLMError('offline')
            info.update(finish_reason=ending, incomplete=ending != 'stop')
        model.stream_chat.side_effect = stream
        with patch.object(engine, 'retrieve', return_value=[source()] if sources is None else sources), patch.object(engine, 'llm', return_value=model):
            return engine.answer_text(question, lang, history=history)

    def assert_blocked(self, answer, **kw):
        text, _, info = self.run_answer(answer, **kw)
        self.assertEqual(info['reason'], 'answer_validation_failed')
        self.assertNotIn(answer, text)
        self.assertEqual(info['generation']['validation']['status'], 'blocked')
        self.assertNotIn(answer, str(info))

    def test_prompt_citation_namespace_is_separate_and_original_unchanged(self):
        s = source(text='The original paragraph.[42]')
        messages = Engine({}).build_messages('Question', 'en', [s])
        self.assertIn('[S1]', str(messages))
        self.assertNotIn('[42]', str(messages))
        self.assertEqual(s['text'], 'The original paragraph.[42]')

    def test_valid_citation_maps_to_display_id_without_claiming_entailment(self):
        text, _, info = self.run_answer('A supported statement [S7].', sources=[source(7)])
        self.assertIn('A supported statement [7].', text)
        validation = info['generation']['validation']
        self.assertEqual(validation['status'], 'passed')
        self.assertEqual(validation['citation_ids'], [7])
        self.assertEqual(validation['claim_support'], 'not_verified')

    def test_numeric_unknown_omitted_and_malformed_references_are_blocked(self):
        for answer in ('Claim [42].', 'Claim [1].', 'Claim [S42].', 'Claim [S2].',
                       'Claim [S1, S2].', 'Claim [S1-2].', 'Claim [^1].', 'Claim [S01].'):
            with self.subTest(answer=answer):
                self.assert_blocked(answer, sources=[source(), source(2, context_omitted=True)])

    def test_no_evidence_cannot_support_a_citation(self):
        self.assert_blocked('Claim [S1].', sources=[])
        text, _, info = self.run_answer('Two plus two is four.', question='What is 2+2?', sources=[])
        self.assertIn('Two plus two is four.', text)
        self.assertEqual(info['mode'], 'llm')

    def test_rejected_text_never_streams_even_before_invalid_citation_arrives(self):
        engine = Engine({})
        model = Mock()
        model.options.return_value = {'context':8192, 'max_tokens':2048, 'context_margin':256}
        model.count_prompt.return_value = 100
        def stream(messages, info):
            yield 'UNRELEASED instruction '
            yield '[S'
            yield '42].'
            info.update(finish_reason='stop', incomplete=False)
        model.stream_chat.side_effect = stream
        with patch.object(engine, 'retrieve', return_value=[source()]), patch.object(engine, 'llm', return_value=model):
            events = list(engine.answer('Question'))
        self.assertNotIn('UNRELEASED', ''.join(v for k,v in events if k=='token'))

    def test_incomplete_and_failed_streams_never_release_partial_instructions(self):
        for ending in ('length','interrupted','error'):
            with self.subTest(ending=ending):
                text, _, info = self.run_answer('UNRELEASED partial instruction [S1].', ending=ending)
                self.assertNotIn('UNRELEASED', text)
                self.assertNotEqual(info['mode'], 'llm')

    def test_cpr_requires_both_conditions_not_unconsciousness_alone(self):
        for answer in ('If unconscious, start CPR [S1].',
                       'If unconscious or not breathing, start CPR [S1].',
                       'Start CPR [S1].'):
            with self.subTest(answer=answer):
                self.assert_blocked(answer, question='He is unconscious after carbon monoxide exposure')
        text, _, info = self.run_answer('If unresponsive and not breathing normally, start CPR [S1].', question='Carbon monoxide exposure')
        self.assertEqual(info['mode'], 'llm')
        self.assertIn('start CPR', text)

    def test_cpr_can_use_stated_facts_but_not_assistant_invented_facts(self):
        good = 'Start CPR [S1].'
        _, _, info = self.run_answer(good, question='My father is unresponsive and not breathing normally')
        self.assertEqual(info['mode'], 'llm')
        self.assert_blocked(good, question='What next?', history=[{'role':'user','content':'Carbon monoxide exposure'}, {'role':'assistant','content':'He is unconscious and not breathing normally'}])
        self.assert_blocked(good, question='He is breathing normally now', history=[{'role':'user','content':'He is unconscious and not breathing normally'}])

    def test_followup_and_topic_reset(self):
        _, _, info = self.run_answer('Start CPR [S1].', question='What next?', history=[{'role':'user','content':'My father is unresponsive and not breathing'}])
        self.assertEqual(info['mode'], 'llm')
        self.assert_blocked('Start CPR [S1].', question='Different problem: carbon monoxide exposure', history=[{'role':'user','content':'My father is unresponsive and not breathing'}])

    def test_portuguese_and_spanish_cpr_conditions(self):
        for lang, q, bad, good in (
            ('pt','Exposição a monóxido de carbono','Se estiver inconsciente ou não respirar, inicie RCP [S1].','Se estiver inconsciente e não respirar normalmente, inicie RCP [S1].'),
            ('es','Exposición a monóxido de carbono','Si está inconsciente, inicie RCP [S1].','Si está inconsciente y no respira normalmente, inicie RCP [S1].')):
            self.assert_blocked(bad, question=q, lang=lang)
            _, _, info = self.run_answer(good, question=q, lang=lang)
            self.assertEqual(info['mode'], 'llm')

    def test_oral_treatment_requires_safe_swallowing_and_responsiveness(self):
        self.assert_blocked('Give oral glucose [S1].', question='My husband is unconscious after insulin')
        self.assert_blocked('Give an antihistamine tablet [S1].', question='My child has a swollen tongue and difficulty breathing after a bee sting')
        for answer, question in (
            ('Do not give anything by mouth [S1].','My husband is unconscious after insulin'),
            ('If awake and able to swallow safely, give oral glucose [S1].','Low blood sugar'),
            ('Give oral glucose [S1].','Low blood sugar. He is awake and able to swallow safely.')):
            _, _, info = self.run_answer(answer, question=question)
            self.assertEqual(info['mode'], 'llm')

    def test_infant_technique_must_not_be_replaced_by_adult_rule(self):
        q = 'My 8-month-old is unconscious and not breathing'
        for answer in ('Pinch the nose and cover the mouth for rescue breaths [S1].',
                       'If untrained, give compressions only [S1].'):
            self.assert_blocked(answer, question=q)
        _, _, info = self.run_answer('Cover the baby’s mouth and nose for rescue breaths [S1].', question=q)
        self.assertEqual(info['mode'], 'llm')

    def test_recognized_actions_need_citations_and_clinician_steps_are_not_regenerated(self):
        self.assert_blocked('Start CPR.', question='My father is unresponsive and not breathing')
        self.assert_blocked('Give 50mL D50W bolus [S1].', question='My husband is unconscious after insulin')

    def test_latest_prior_user_turn_overrides_older_patient_state(self):
        self.assert_blocked('Start CPR [S1].', question='What next?', history=[
            {'role':'user','content':'My father is unconscious and not breathing'},
            {'role':'user','content':'He is breathing normally now'}])

    def test_conditions_must_belong_to_the_action_and_must_be_conjunctive(self):
        for answer in ('If awake or able to swallow safely, give oral glucose [S1].',
                       'If unresponsive and not breathing normally, call for help; if unconscious, start CPR [S1].'):
            self.assert_blocked(answer, question='Carbon monoxide exposure')
        self.assert_blocked('If awake and able to swallow safely, give antihistamine tablets [S1].', question='My child has a swollen tongue and difficulty swallowing')

    def test_common_action_variants_are_checked(self):
        for answer in ('Give glucose [S1].', 'Give sugar [S1].'):
            self.assert_blocked(answer, question='My husband is unconscious after insulin')
        self.assert_blocked('CPR immediately [S1].', question='He is unconscious after carbon monoxide exposure')
        _, _, info = self.run_answer('If awake and able to swallow safely, give sugar [S1].', question='Low blood sugar')
        self.assertEqual(info['mode'], 'llm')

    def test_model_cannot_attach_a_different_link_to_an_application_citation(self):
        for answer in ('Claim [S1](https://example.org/wrong).', 'Claim [S1][other].', '![S1](https://example.org/wrong)'):
            self.assert_blocked(answer)

    def test_code_indices_are_not_citations_but_coding_cannot_hide_emergency_actions(self):
        _, _, info = self.run_answer('Use `x[1]` to get the second item.\n```python\nx = [1, 2]\n```', question='How do I index a Python list?', sources=[])
        self.assertEqual(info['mode'], 'llm')
        self.assert_blocked('`Start CPR [S1].`', question='He is unconscious after carbon monoxide exposure')

    def test_captured_failures_are_rejected_after_valid_citations_are_migrated(self):
        import json
        from pathlib import Path
        from app.answer_validation import validate_answer
        cases = json.loads((Path(__file__).parent / 'fixtures/answer_release.json').read_text())
        required = {'cpr':'invasive_procedure', 'portuguese':'cpr_prerequisites_missing',
                    'infant_followup':'infant_technique_mismatch', 'anaphylaxis':'oral_intake_prerequisites_missing',
                    'stroke':'invalid_citation_format', 'diabetes':'clinical_infusion_dosing'}
        for case in cases:
            req = case['request']
            rendered, report = validate_answer(case['answer'], case['sources'], req['q'], req['lang'], req['history'])
            with self.subTest(case=case['id']):
                self.assertEqual(rendered, '')
                self.assertIn(required[case['id']], report['issues'])

    def test_response_buffer_is_bounded(self):
        self.assert_blocked('x' * 131073)

    def test_reversed_oral_conditions_are_conjunctive(self):
        self.assert_blocked('If able to swallow safely or awake, give glucose [S1].', question='Low blood sugar')
        _, _, info = self.run_answer('If able to swallow safely and awake, give glucose [S1].', question='Low blood sugar')
        self.assertEqual(info['mode'], 'llm')

    def test_latest_sentence_in_prior_turn_overrides_older_state(self):
        self.assert_blocked('Start CPR [S1].', question='What next?', history=[{'role':'user','content':'He is unconscious and not breathing. He is breathing normally now.'}])

    def test_recipes_are_not_oral_medical_treatment(self):
        for question, answer, lang in (
            ('How do I make a cake?', 'Take one cup of sugar [S1].', 'en'),
            ('Como fazer um bolo?', 'Use uma xícara de açúcar [S1].', 'pt')):
            _, _, info = self.run_answer(answer, question=question, lang=lang)
            self.assertEqual(info['mode'], 'llm')

    def test_rescuer_condition_does_not_override_known_patient_facts(self):
        _, _, info = self.run_answer('If alone, start CPR [S1].', question='He is unresponsive and not breathing')
        self.assertEqual(info['mode'], 'llm')

    def test_negated_gasping_is_not_abnormal_breathing(self):
        self.assert_blocked('Start CPR [S1].', question='He is unconscious, breathing normally and not gasping')

    def test_food_and_drink_warning_is_not_an_instruction_to_drink(self):
        for answer in ('Do not give food or drink [S1].', 'Do not give food, drink, or tablets [S1].'):
            _, _, info = self.run_answer(answer, question='My mother has stroke symptoms')
            self.assertEqual(info['mode'], 'llm')
        self.assert_blocked('Drink juice [S1].', question='My husband is unconscious after insulin')

    def test_known_facts_do_not_license_an_invalid_oral_condition(self):
        q = 'Low blood sugar. He is awake and able to swallow safely.'
        for answer in ('If unconscious, give oral glucose [S1].', 'If awake or able to swallow safely, give oral glucose [S1].'):
            self.assert_blocked(answer, question=q)
        _, _, info = self.run_answer('If awake and able to swallow safely, give glucose or juice [S1].', question='Low blood sugar')
        self.assertEqual(info['mode'], 'llm')

    def test_action_heading_can_use_its_cited_section_but_not_another_section(self):
        q = 'My father is unresponsive and not breathing'
        _, _, info = self.run_answer('### Start CPR\nFollow the supplied procedure [S1].', question=q)
        self.assertEqual(info['mode'], 'llm')
        self.assert_blocked('### Start CPR\nUncited procedure.\n### Other\nOther statement [S1].', question=q)

    def test_extractive_display_separates_original_footnotes_from_app_citations(self):
        original = source(text='Original wording.[42]')
        text = Engine({}).extractive_answer('en', [original])
        self.assertIn('### [1]', text)
        self.assertNotIn('[42]', text)
        self.assertEqual(original['text'], 'Original wording.[42]')

    def test_negative_attempt_is_not_positive_administration(self):
        _, _, info = self.run_answer('Do not attempt to give juice or honey [S1].', question='My husband is unconscious after insulin')
        self.assertEqual(info['mode'], 'llm')

    def test_conditional_breathing_check_can_use_stated_unresponsiveness(self):
        _, _, info = self.run_answer('If not breathing normally, start CPR [S1].', question='My father is unresponsive after carbon monoxide exposure')
        self.assertEqual(info['mode'], 'llm')
        self.assert_blocked('If breathing normally, start CPR [S1].', question='My father is unresponsive and not breathing normally')

    def test_oversized_citation_id_is_rejected_without_integer_conversion(self):
        self.assert_blocked('Claim [S' + '9' * 4301 + '].')

    def test_source_body_cannot_reintroduce_application_citation_tokens(self):
        s = source(text='Internal document reference [S1] and footnote [42].')
        prompt = Engine({}).build_messages('Question', 'en', [s])[-1]['content']
        self.assertEqual(prompt.count('[S1]'), 1)
        self.assertIn('[S1]', s['text'])
