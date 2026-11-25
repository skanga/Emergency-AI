import unittest
from unittest.mock import Mock
from tests.manual.retrieval_eval import measure_gold, summarize, evaluate_case


class EvaluationTests(unittest.TestCase):
    def test_omitted_references_do_not_count_as_prompt_recall(self):
        case = {'gold_passages':[{'served_name':'medicine_1','article':'Aid','anchor':'Treatment'}]}
        source = {'kind':'kiwix','link':'/content/medicine_1/Aid#Treatment','context_omitted':True}
        self.assertFalse(measure_gold(case,[source])['matched'])
        source['context_omitted'] = False
        self.assertTrue(measure_gold(case,[source])['matched'])

    def test_unannotated_cases_are_not_silently_counted_as_success(self):
        results = [{'language':'en','seconds':1,'gold':{'annotated':True,'matched':True}},
                   {'language':'pt','seconds':2,'gold':{'annotated':True,'matched':False}},
                   {'language':'es','seconds':3,'gold':{'annotated':False,'matched':False}}]
        summary = summarize(results)
        self.assertEqual(summary['gold_recall'], {'matched':1,'annotated':2,'rate':.5})
        self.assertIsNone(summary['human_precision'])
        self.assertFalse(summary['release_gates_passed'])

    def test_reviewed_precedence_still_gets_real_token_fitting(self):
        engine = Mock()
        source = {'id':'preferred','n':1,'kind':'kiwix','link':'/content/medicine_1/Aid#Treatment'}
        def retrieve(*args, **kwargs):
            kwargs['diagnostics']['conflicts'] = [{'resolution':'reviewed_precedence','preferred_source':'preferred'}]
            return [source]
        engine.retrieve.side_effect = retrieve
        engine.build_messages.return_value = []
        engine.fit_messages.return_value = ([], [dict(source,context_omitted=True)], {})
        case = {'id':'test','q':'question','gold_passages':[{'served_name':'medicine_1','article':'Aid','anchor':'Treatment'}]}
        result = evaluate_case(engine,case)
        engine.fit_messages.assert_called_once()
        self.assertEqual(result['blocked_reason'], 'reviewed_source_omitted')
        self.assertFalse(result['gold']['matched'])

    def test_generation_does_not_restore_blocked_gold(self):
        engine = Mock()
        source = {'id':'other','n':1,'kind':'kiwix','link':'/content/medicine_1/Aid#Treatment'}
        engine.retrieve.return_value = [source]
        engine.build_messages.return_value = []
        engine.fit_messages.return_value = ([],[source],{})
        engine.answer_text.return_value = ('Withheld',[source],{'reason':'reviewed_source_omitted','retrieval':{'status':'success'}})
        case = {'id':'test','q':'question','gold_passages':[{'served_name':'medicine_1','article':'Aid','anchor':'Treatment'}]}
        result = evaluate_case(engine,case,generate=True)
        self.assertFalse(result['gold']['matched'])
        self.assertEqual(result['blocked_reason'],'reviewed_source_omitted')
        self.assertEqual(result['messages'],[])
