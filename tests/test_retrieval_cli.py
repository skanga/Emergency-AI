import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.retrieval_cli import diagnose, index_libraries, summary_text
import emergency


class RetrievalCliTests(unittest.TestCase):
    def test_diagnose_does_not_generate_or_persist_by_default(self):
        args = SimpleNamespace(text=['A question'], lang='en', libraries=None, output=None)
        with patch('app.retrieval_cli.Engine') as engine, contextlib.redirect_stdout(io.StringIO()) as output:
            engine.return_value.retrieve.return_value = []
            self.assertEqual(diagnose(args, {}), 0)
        engine.return_value.llm.assert_not_called()
        engine.return_value.answer.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['question'], 'A question')

    def test_missing_extractor_does_not_download_during_index_command(self):
        args = SimpleNamespace(libraries='medicine', prepare_tool=False, cleanup=False)
        with patch('app.retrieval_cli.tool_status', return_value={'state':'extractor_missing'}), patch('app.retrieval_cli.prepare_tool') as prepare, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(index_libraries(args, {}), 2)
        prepare.assert_not_called()

    def test_answer_prints_retrieval_failures_and_omissions(self):
        source = {'kind':'kiwix','n':1,'doc_title':'Medicine','section':'Aid','link':'/content/a','context_omitted':True,'context_omitted_reason':'token_budget'}
        engine = SimpleNamespace(answer=lambda *a,**k: iter([('retrieval',{'libraries':[{'name':'medicine','status':'http_error'}]}),('sources',[source]),('token','Fallback'),('done',{'mode':'search'})]))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            emergency._print_answer(engine,'question','en',[])
        self.assertIn('Library passages used: 0',output.getvalue())
        self.assertIn('medicine: search failed',output.getvalue())
        self.assertIn('not used',output.getvalue())
        self.assertIn('Model context limit',output.getvalue())

    def test_fetch_failure_is_distinct_from_successful_native_search(self):
        report = {'status':'failed','libraries':[{'name':'medicine','status':'success'}],'fetches':[{'status':'http_error'}]}
        self.assertIn('Article fetch failures: 1',summary_text(report,[]))
        self.assertIn('none selected',summary_text({'status':'no_selection','libraries':[]},[]))

    def test_conflict_notice_survives_interruption_before_tokens(self):
        def events(*args,**kwargs):
            yield 'retrieval', {'conflicts':[{'resolution':'unresolved'}]}
            raise KeyboardInterrupt()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(KeyboardInterrupt):
                emergency._print_answer(SimpleNamespace(answer=events),'question','en',[])
        self.assertIn('Sources disagree',output.getvalue())
