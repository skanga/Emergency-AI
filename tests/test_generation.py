"""Generation contracts: budgets, backend controls and incomplete streams."""
import io
import json
import unittest
from unittest.mock import patch

from app.engine import Engine
from app.llm import OpenAICompatible, Ollama, LLMError


def sse(*chunks):
    return io.BytesIO(b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks))


class GenerationTests(unittest.TestCase):
    def test_llama_controls_and_reasoning_are_separate(self):
        client = OpenAICompatible('http://localhost/v1', backend='llamacpp',
                                  settings={'llm_thinking': True, 'llm_max_tokens': 4096})
        result = {}
        response = sse({'choices': [{'delta': {'reasoning_content': 'private'}}]},
                       {'choices': [{'delta': {'content': 'Answer'}, 'finish_reason': 'stop'}]})
        with patch.object(client, 'count_prompt', return_value=10), \
                patch('app.llm.open_url', return_value=response) as request:
            self.assertEqual(''.join(client.stream_chat([], result)), 'Answer')
        payload = request.call_args.kwargs['data']
        self.assertEqual(payload['max_tokens'], 4096)
        self.assertTrue(payload['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(payload['reasoning_format'], 'deepseek')
        self.assertFalse(result['incomplete'])
        self.assertTrue(result['reasoning_present'])
        self.assertNotIn('private', str(result))

    def test_generic_api_does_not_receive_llama_extensions(self):
        client = OpenAICompatible('http://localhost/v1')
        with patch('app.llm.open_url', return_value=sse({'choices': [{'finish_reason': 'stop'}]})) as request:
            list(client.stream_chat([]))
        payload = request.call_args.kwargs['data']
        self.assertNotIn('chat_template_kwargs', payload)
        self.assertNotIn('reasoning_format', payload)
        self.assertEqual(payload['max_tokens'], 2048)

    def test_ollama_named_thinking_and_context(self):
        client = Ollama('http://localhost', 'example:latest', settings={
            'llm_thinking': 'high', 'llm_context': 16384, 'llm_max_tokens': 4096})
        response = io.BytesIO((json.dumps({'message': {'thinking': 'private', 'content': 'Answer'},
                                          'done': True, 'done_reason': 'length'}) + '\n').encode())
        result = {}
        with patch('app.llm.open_url', return_value=response) as request:
            self.assertEqual(''.join(client.stream_chat([], result)), 'Answer')
        payload = request.call_args.kwargs['data']
        self.assertEqual(payload['think'], 'high')
        self.assertEqual(payload['options']['num_ctx'], 16384)
        self.assertEqual(payload['options']['num_predict'], 4096)
        self.assertTrue(result['incomplete'])
        self.assertEqual(result['finish_reason'], 'length')

    def test_split_inline_thinking_is_never_displayed(self):
        pieces = ['<thi', 'nk>private', '</th', 'ink>Answer']
        client = OpenAICompatible('http://localhost/v1')
        response = sse(*[{'choices': [{'delta': {'content': p}}]} for p in pieces],
                       {'choices': [{'finish_reason': 'stop'}]})
        with patch('app.llm.open_url', return_value=response):
            self.assertEqual(''.join(client.stream_chat([])), 'Answer')

    def test_length_and_broken_stream_are_not_complete(self):
        for ending, reason in [({'choices': [{'finish_reason': 'length'}]}, 'length'),
                               ({}, 'interrupted')]:
            client = OpenAICompatible('http://localhost/v1')
            result = {}
            with patch('app.llm.open_url', return_value=sse(
                    {'choices': [{'delta': {'content': 'Partial'}}]}, ending)):
                self.assertEqual(''.join(client.stream_chat([], result)), 'Partial')
            self.assertTrue(result['incomplete'])
            self.assertEqual(result['finish_reason'], reason)

    def test_profile_precedence_and_exact_model_matching(self):
        from app.generation import generation_options
        settings = {'llm_max_tokens': 2100,
                    'llm_backend_settings': {'ollama': {'max_tokens': 3000}},
                    'llm_model_settings': {'ollama': {'qwen:4b': {'max_tokens': 4000}}}}
        self.assertEqual(generation_options(settings, 'ollama', 'qwen:4b')['max_tokens'], 4000)
        self.assertEqual(generation_options(settings, 'ollama', 'qwen:8b')['max_tokens'], 3000)
        self.assertEqual(generation_options(settings, 'openai', 'qwen:4b')['max_tokens'], 2100)

    def test_impossible_budget_rejected_before_request(self):
        client = Ollama('http://localhost', 'test', settings={'llm_context': 1024, 'llm_max_tokens': 2048})
        with patch('app.llm.open_url') as request, self.assertRaises(LLMError):
            list(client.stream_chat([]))
        request.assert_not_called()

    def test_llama_counts_rendered_prompt_with_server_tokenizer(self):
        client = OpenAICompatible('http://localhost/v1', backend='llamacpp')
        with patch('app.llm.open_url', side_effect=[io.BytesIO(b'{"prompt":"rendered"}'),
                                                   io.BytesIO(b'{"tokens":[1,2,3]}')]) as request:
            self.assertEqual(client.count_prompt([{'role': 'user', 'content': 'Hi'}]), 3)
        self.assertTrue(request.call_args.args[0].endswith('/tokenize'))
        self.assertEqual(request.call_args.kwargs['data']['content'], 'rendered')

    def test_fallback_count_accounts_for_utf8_and_roles(self):
        client = Ollama('http://localhost', 'test')
        messages = [{'role': 'user', 'content': '\u6c34' * 100}]
        self.assertGreaterEqual(client.count_prompt(messages), 300)

    def test_engine_warns_on_truncation_in_text_and_metadata(self):
        engine = Engine({'llm_backend': 'none', 'kiwix_enabled': False})
        client = OpenAICompatible('http://localhost/v1')
        source = {'n': 1, 'kind': 'kit', 'doc_title': 'Guide', 'section': 'Steps', 'text': 'Complete source.'}
        with patch.object(engine, 'retrieve', return_value=[source]), patch.object(engine, 'llm', return_value=client), \
                patch('app.llm.open_url', return_value=sse(
                    {'choices': [{'delta': {'content': 'Partial'}, 'finish_reason': 'length'}]})):
            text, _, info = engine.answer_text('Question')
        self.assertIn('incomplete', text.lower())
        self.assertEqual(info['generation']['finish_reason'], 'length')

    def test_context_fitting_drops_whole_sources_and_keeps_question(self):
        engine = Engine({'llm_backend': 'none', 'kiwix_enabled': False})
        client = Ollama('http://localhost', 'test', settings={'llm_context': 3000, 'llm_max_tokens': 1000})
        sources = [{'n': i, 'kind': 'kit', 'doc_title': 'Guide', 'section': 'Steps',
                    'text': 'SECTION' + str(i) + 'x' * 900} for i in (1, 2)]
        messages, fitted, report = engine.fit_messages(client, 'Question', 'en', sources,
            [{'role': 'user', 'content': 'old' * 1000}, {'role': 'assistant', 'content': 'old answer'}])
        self.assertIn('Question', messages[-1]['content'])
        self.assertNotIn('old answer', str(messages))
        self.assertTrue(any(s.get('context_omitted') for s in fitted))
        for s in fitted:
            if not s.get('context_omitted'):
                self.assertIn(s['text'], messages[-1]['content'])
        self.assertLessEqual(report['input_tokens'] + 1000 + 256, 3000)

    def test_oversized_question_falls_back_without_generation(self):
        engine = Engine({'llm_backend': 'none', 'kiwix_enabled': False})
        client = Ollama('http://localhost', 'test')
        source = {'n': 1, 'kind': 'kit', 'doc_title': 'Guide', 'section': 'Steps', 'text': 'Full passage.'}
        with patch.object(engine, 'retrieve', return_value=[source]), patch.object(engine, 'llm', return_value=client), \
                patch('app.llm.open_url') as request:
            text, _, info = engine.answer_text('q' * 20000)
        request.assert_not_called()
        self.assertEqual(info['mode'], 'search')
        self.assertIn('Full passage.', text)

    def test_running_llama_context_limits_configured_context(self):
        client = OpenAICompatible('http://localhost/v1', backend='llamacpp')
        with patch('app.llm.get_json', side_effect=[{'data': [{'id': 'test.gguf'}]},
                                                   {'default_generation_settings': {'n_ctx': 4096}}]):
            self.assertTrue(client.available())
        self.assertEqual(client.options()['context'], 4096)

    def test_auto_backend_keeps_generic_servers_free_of_extensions(self):
        from app.llm import detect_llm
        with patch('app.llm.get_json', side_effect=[{'data': [{'id': 'test'}]}, OSError('no props')]):
            client = detect_llm({'llm_backend': 'auto'})
        self.assertEqual(client.backend, 'openai')
        self.assertEqual(client.thinking_params(), {})

    def test_invalid_profiles_are_rejected(self):
        from app.generation import generation_options
        for overrides in ({'max_tokens': -1}, {'context': True}, {'temperature': float('nan')},
                          {'thinking': 7}, {'typo': 1}, {'max_tokens': 8192}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                generation_options({'llm_backend_settings': {'ollama': overrides}}, 'ollama', 'test')

    def test_reasoning_only_limit_falls_back_to_passages(self):
        engine = Engine({'llm_backend': 'none', 'kiwix_enabled': False})
        client = OpenAICompatible('http://localhost/v1')
        source = {'n': 1, 'kind': 'kit', 'doc_title': 'Guide', 'section': 'Steps', 'text': 'Full passage.'}
        with patch.object(engine, 'retrieve', return_value=[source]), patch.object(engine, 'llm', return_value=client), \
                patch('app.llm.open_url', return_value=sse(
                    {'choices': [{'delta': {'reasoning_content': 'private'}, 'finish_reason': 'length'}]})):
            text, _, info = engine.answer_text('Question')
        self.assertNotIn('private', text)
        self.assertIn('Full passage.', text)
        self.assertIn('Incomplete answer', text)
        self.assertEqual(info['mode'], 'search')

    def test_launcher_uses_same_model_context_override(self):
        from app.launcher import Launcher
        settings = {'llm_model_settings': {'llamacpp': {'test.gguf': {'context': 16384}}}}
        launcher = Launcher(settings, say=lambda *_: None)
        with patch('app.launcher.port_in_use', return_value=False), \
                patch('app.launcher.find_llama_server', return_value=('llama-server', 'llamacpp')), \
                patch('app.launcher.find_model', return_value='/models/test.gguf'), \
                patch('app.launcher._ensure_exec'), patch('app.launcher._spawn') as spawn:
            self.assertTrue(launcher.start_llm())
        command = spawn.call_args.args[0]
        self.assertEqual(command[command.index('-c') + 1], '16384')
