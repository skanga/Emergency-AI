"""Clients for local language models.

Supports:
  * llama.cpp `llama-server`, llamafile, LM Studio, KoboldCpp, Jan... (OpenAI-compatible API)
  * Ollama (native API)

Everything runs on this computer — no requests go to the internet.
"""

import json
from http.client import HTTPException

from .net import get_json, open_url
from .generation import AnswerFilter, generation_options


class LLMError(Exception):
    pass


class GenerationClient:
    def options(self):
        try:
            options = generation_options(self.settings, self.backend, self.model_key())
        except ValueError as e:
            raise LLMError(str(e)) from e
        if getattr(self, 'server_context', None):
            options['context'] = min(options['context'], self.server_context)
        if options['max_tokens'] + options['context_margin'] >= options['context']:
            raise LLMError('Output budget exceeds the running server context window')
        return options

    def model_key(self):
        return self.model

    def count_prompt(self, messages):
        # Conservative fallback for APIs without a tokenizer. UTF-8 bytes
        # avoid the optimistic chars/4 assumption for multilingual input.
        return 32 + sum(len(m['content'].encode('utf-8')) +
                        len(m['role'].encode('utf-8')) + 32 for m in messages)

    def check_prompt(self, messages, result):
        options = self.options()
        count = self.count_prompt(messages)
        result.update(input_tokens=count, max_tokens=options['max_tokens'],
                      context=options['context'], context_margin=options['context_margin'])
        if count + options['max_tokens'] + options['context_margin'] > options['context']:
            raise LLMError('The question and sources exceed the input context budget')
        return options


class OpenAICompatible(GenerationClient):
    name = "llama.cpp"

    def __init__(self, base_url, model="local", max_tokens=2048, temperature=0.2,
                 backend="openai", settings=None):
        self.base_url = base_url.rstrip("/")
        self.root_url = self.base_url[:-3] if self.base_url.endswith('/v1') else self.base_url
        self.model = model
        self.backend = backend
        self.settings = {'llm_max_tokens': max_tokens, 'llm_temperature': temperature}
        self.settings.update(settings or {})
        self.server_context = None

    def model_key(self):
        return self.model.replace('\\', '/').rsplit('/', 1)[-1] if self.backend == 'llamacpp' else self.model

    def count_prompt(self, messages):
        if self.backend == 'llamacpp':
            try:
                payload = {'messages': messages, **self.thinking_params()}
                with open_url(self.root_url + '/apply-template', data=payload, timeout=5) as response:
                    prompt = json.load(response)['prompt']
                with open_url(self.root_url + '/tokenize', data={
                        'content': prompt, 'add_special': True, 'parse_special': True}, timeout=5) as response:
                    tokens = json.load(response)['tokens']
                if isinstance(tokens, list):
                    return len(tokens)
            except (OSError, ValueError, KeyError, TypeError, HTTPException):
                pass
        return super().count_prompt(messages)

    def thinking_params(self):
        thinking = self.options()['thinking']
        params = {}
        if self.backend == 'llamacpp':
            params['reasoning_format'] = 'deepseek'
            if type(thinking) is bool:
                params['chat_template_kwargs'] = {'enable_thinking': thinking}
                if not thinking:
                    params['reasoning_effort'] = 'none'
            elif isinstance(thinking, str):
                params['reasoning_effort'] = thinking
        elif isinstance(thinking, str):
            params['reasoning_effort'] = thinking
        return params

    def available(self):
        try:
            data = get_json(self.base_url + "/models", timeout=2)
            models = data.get("data") or data.get("models") or []
            if models:
                first = models[0]
                self.model = first.get("id") or first.get("name") or self.model
            if self.backend in ('auto', 'llamacpp'):
                auto = self.backend == 'auto'
                if auto:
                    self.backend = 'openai'
                try:
                    props = get_json(self.root_url + '/props', timeout=2)
                    context = props.get('default_generation_settings', {}).get('n_ctx')
                    if type(context) is int and context > 0:
                        self.server_context = context
                        if auto:
                            self.backend = 'llamacpp'
                except (OSError, ValueError, TypeError, AttributeError, HTTPException):
                    pass
            return True
        except Exception:
            return False

    def describe(self):
        return {"backend": self.name, "model": self.model.split("/")[-1].split("\\")[-1], "url": self.base_url}

    def stream_chat(self, messages, result=None):
        result = result if result is not None else {}
        result.update(finish_reason=None, incomplete=False, reasoning_present=False)
        options = self.check_prompt(messages, result)
        payload = {
            "model": self.model, "messages": messages, "stream": True,
            "max_tokens": options['max_tokens'], "temperature": options['temperature'],
            **self.thinking_params(),
        }
        answer = AnswerFilter()
        try:
            with open_url(self.base_url + "/chat/completions", data=payload, timeout=600) as response:
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line.startswith('data:'):
                        continue
                    data = line[5:].strip()
                    if data == '[DONE]':
                        break
                    try:
                        obj = json.loads(data)
                    except ValueError as e:
                        raise LLMError('Invalid model response') from e
                    if obj.get('error'):
                        raise LLMError('Model server reported a generation error')
                    choices = obj.get('choices') or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get('delta') or {}
                    if delta.get('reasoning_content') or delta.get('reasoning'):
                        result['reasoning_present'] = True
                    text = answer.feed(delta.get('content') or choice.get('text') or '')
                    if text:
                        yield text
                    if choice.get('finish_reason'):
                        result['finish_reason'] = choice['finish_reason']
            answer.finish()
            result['reasoning_present'] |= answer.seen
            result['finish_reason'] = result['finish_reason'] or 'interrupted'
            result['incomplete'] = result['finish_reason'] != 'stop' or answer.thinking
        except (OSError, ValueError, HTTPException) as e:
            raise LLMError(str(e)) from e


class Ollama(GenerationClient):
    name = "ollama"

    def __init__(self, base_url, model, max_tokens=2048, temperature=0.2, settings=None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.backend = 'ollama'
        self.settings = {'llm_max_tokens': max_tokens, 'llm_temperature': temperature}
        self.settings.update(settings or {})

    def available(self):
        try:
            data = get_json(self.base_url + "/api/tags", timeout=2)
            names = [m.get("name", "") for m in data.get("models", [])]
            if not names:
                return False
            requested = self.model if ":" in self.model.rsplit("/", 1)[-1] else self.model + ":latest"
            if requested not in names:
                return False
            self.model = requested
            return True
        except Exception:
            return False

    def describe(self):
        return {"backend": self.name, "model": self.model, "url": self.base_url}

    def stream_chat(self, messages, result=None):
        result = result if result is not None else {}
        result.update(finish_reason=None, incomplete=False, reasoning_present=False)
        options = self.check_prompt(messages, result)
        payload = {
            "model": self.model, "messages": messages, "stream": True,
            "options": {"temperature": options['temperature'], "num_predict": options['max_tokens'],
                        "num_ctx": options['context']},
        }
        if options['thinking'] is not None:
            payload['think'] = options['thinking']
        answer = AnswerFilter()
        try:
            with open_url(self.base_url + '/api/chat', data=payload, timeout=600) as response:
                for raw in response:
                    if not raw.strip():
                        continue
                    try:
                        obj = json.loads(raw)
                    except ValueError as e:
                        raise LLMError('Invalid model response') from e
                    if obj.get('error'):
                        raise LLMError('Model server reported a generation error')
                    message = obj.get('message') or {}
                    if message.get('thinking'):
                        result['reasoning_present'] = True
                    text = answer.feed(message.get('content') or '')
                    if text:
                        yield text
                    if obj.get('done'):
                        result['finish_reason'] = obj.get('done_reason') or 'unknown'
                        break
            answer.finish()
            result['reasoning_present'] |= answer.seen
            result['finish_reason'] = result['finish_reason'] or 'interrupted'
            result['incomplete'] = result['finish_reason'] != 'stop' or answer.thinking
        except (OSError, ValueError, HTTPException) as e:
            raise LLMError(str(e)) from e


def detect_llm(settings):
    """Return an available client or None (search-only mode)."""
    backend = settings.get("llm_backend", "auto")
    max_tokens = settings.get("llm_max_tokens", 2048)
    temperature = settings.get("llm_temperature", 0.2)
    candidates = []
    if backend in ("auto", "openai", "llamacpp"):
        candidates.append(OpenAICompatible(settings.get("llm_url", "http://127.0.0.1:8091/v1"),
                                           max_tokens=max_tokens, temperature=temperature, settings=settings,
                                           backend=backend))
    if backend in ("auto", "ollama"):
        candidates.append(Ollama(settings.get("ollama_url", "http://127.0.0.1:11434"),
                                 settings.get("ollama_model", "qwen2.5:3b"),
                                 max_tokens=max_tokens, temperature=temperature, settings=settings))
    if backend == "none":
        return None
    for c in candidates:
        if c.available():
            return c
    return None
