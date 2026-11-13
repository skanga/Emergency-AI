"""Clients for local language models.

Supports:
  * llama.cpp `llama-server`, llamafile, LM Studio, KoboldCpp, Jan... (OpenAI-compatible API)
  * Ollama (native API)

Everything runs on this computer — no requests go to the internet.
"""

import json

from .net import get_json, open_url


class LLMError(Exception):
    pass


class OpenAICompatible:
    name = "llama.cpp"

    def __init__(self, base_url, model="local", max_tokens=900, temperature=0.2):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def available(self):
        try:
            data = get_json(self.base_url + "/models", timeout=2)
            models = data.get("data") or data.get("models") or []
            if models:
                first = models[0]
                self.model = first.get("id") or first.get("name") or self.model
            return True
        except Exception:
            return False

    def describe(self):
        return {"backend": self.name, "model": self.model.split("/")[-1].split("\\")[-1], "url": self.base_url}

    def stream_chat(self, messages):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        try:
            resp = open_url(self.base_url + "/chat/completions", data=payload, timeout=600)
        except Exception as e:
            raise LLMError(str(e))
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content") or choices[0].get("text") or ""
                if text:
                    yield text


class Ollama:
    name = "ollama"

    def __init__(self, base_url, model, max_tokens=900, temperature=0.2):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

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

    def stream_chat(self, messages):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        try:
            resp = open_url(self.base_url + "/api/chat", data=payload, timeout=600)
        except Exception as e:
            raise LLMError(str(e))
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                text = (obj.get("message") or {}).get("content") or ""
                if text:
                    yield text
                if obj.get("done"):
                    break


def detect_llm(settings):
    """Return an available client or None (search-only mode)."""
    backend = settings.get("llm_backend", "auto")
    max_tokens = settings.get("llm_max_tokens", 900)
    temperature = settings.get("llm_temperature", 0.2)
    candidates = []
    if backend in ("auto", "openai", "llamacpp"):
        candidates.append(OpenAICompatible(settings.get("llm_url", "http://127.0.0.1:8091/v1"),
                                           max_tokens=max_tokens, temperature=temperature))
    if backend in ("auto", "ollama"):
        candidates.append(Ollama(settings.get("ollama_url", "http://127.0.0.1:11434"),
                                 settings.get("ollama_model", "qwen2.5:3b"),
                                 max_tokens=max_tokens, temperature=temperature))
    if backend == "none":
        return None
    for c in candidates:
        if c.available():
            return c
    return None
