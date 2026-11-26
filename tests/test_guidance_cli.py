"""The CLI accepts source-backed fallback sources as well as kit/Kiwix."""
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import Mock

import emergency


class GuidanceCLITests(unittest.TestCase):
    def test_guidance_source_does_not_require_local_guide_keys(self):
        source = {'n':1, 'kind':'guidance', 'doc_title':'Reference', 'section':'Advice',
                  'url':'https://example.org/reference', 'text':'Useful help', 'fallback_evidence':True}
        engine = Mock()
        engine.answer.return_value = iter([('sources',[source]), ('token','Useful help [1].'),
                                           ('done',{'mode':'fallback','seconds':1})])
        output = io.StringIO()
        with redirect_stdout(output):
            answer = emergency._print_answer(engine, 'Help', 'en', [])
        self.assertEqual(answer, 'Useful help [1].')
        self.assertIn('https://example.org/reference', output.getvalue())
        self.assertIn('source-backed fallback', output.getvalue())
