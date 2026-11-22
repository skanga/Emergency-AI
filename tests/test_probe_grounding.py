import io
import unittest
import json
from unittest.mock import patch

from scripts.probe_grounding import ask, read_answer


class ProbeGroundingTests(unittest.TestCase):
    def test_collects_events(self):
        stream = io.BytesIO(b'event: sources\ndata: []\n\nevent: token\ndata: "Hello"\n\n'
                            b'event: done\ndata: {"mode":"llm","sources_supplied":false}\n\n')
        result = read_answer(stream)
        self.assertEqual('Hello', result['answer'])
        self.assertFalse(result['info']['sources_supplied'])

    def test_request_uses_fresh_history_and_selected_library_mode(self):
        response = io.BytesIO(b'event: done\ndata: {"mode":"search"}\n\n')
        with patch('scripts.probe_grounding.urlopen', return_value=response) as request:
            ask('http://localhost:8090/', 'fibonacci', 10, False)
        sent = request.call_args.args[0]
        self.assertEqual('http://localhost:8090/api/ask', sent.full_url)
        payload = json.loads(sent.data)
        self.assertEqual([], payload['history'])
        self.assertFalse(payload['use_kiwix'])
        self.assertTrue(payload['use_llm'])

    def test_rejects_missing_completion(self):
        with self.assertRaisesRegex(RuntimeError, 'completion'):
            read_answer(io.BytesIO(b'event: token\ndata: "partial"\n\n'))

    def test_surfaces_server_errors(self):
        with self.assertRaisesRegex(RuntimeError, 'busy'):
            read_answer(io.BytesIO(b'event: error\ndata: {"error":"busy"}\n\n'))
