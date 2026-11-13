"""Generation policy shared by the launcher and local API clients."""
import math


def generation_options(settings, backend, model):
    """Global defaults < backend overrides < exact backend/model overrides."""
    options = {key: settings.get('llm_' + key, default) for key, default in (
        ('max_tokens', 2048), ('context', 8192), ('temperature', 0.2),
        ('thinking', None if backend == 'openai' else False), ('context_margin', 256))}
    for field in ('llm_backend_settings', 'llm_model_settings'):
        mapping = settings.get(field, {})
        if not isinstance(mapping, dict):
            raise ValueError(field + ' must be an object')
        override = mapping.get(backend, {})
        if field == 'llm_model_settings':
            if not isinstance(override, dict):
                raise ValueError(field + ' backend entry must be an object')
            override = override.get(model, {})
        if not isinstance(override, dict) or set(override) - set(options):
            raise ValueError('Invalid generation settings in ' + field)
        options.update(override)
    for key in ('max_tokens', 'context', 'context_margin'):
        value = options[key]
        if type(value) is not int or value < (0 if key == 'context_margin' else 1):
            raise ValueError(key + ' must be a positive integer (margin may be zero)')
    if options['max_tokens'] + options['context_margin'] >= options['context']:
        raise ValueError('Output budget plus context margin must be smaller than the context window')
    temp = options['temperature']
    if type(temp) not in (int, float) or not math.isfinite(temp) or not 0 <= temp <= 2:
        raise ValueError('temperature must be a number between 0 and 2')
    thinking = options['thinking']
    if thinking is not None and type(thinking) is not bool and not (isinstance(thinking, str) and thinking.strip()):
        raise ValueError('thinking must be true, false, null, or a supported effort name')
    if backend == 'openai' and type(thinking) is bool:
        raise ValueError('Generic OpenAI-compatible servers need a supported thinking effort name or null')
    return options


class AnswerFilter:
    """Suppress inline <think> blocks even when tags span stream chunks.

    Prefer the backend's separate reasoning field; this is a fallback for
    servers returning raw tagged text. No reasoning trace is retained.
    """
    def __init__(self):
        self.pending = ''
        self.thinking = False
        self.seen = False

    def feed(self, text):
        self.pending += text
        output = []
        while self.pending:
            tag = '</think>' if self.thinking else '<think>'
            pos = self.pending.find(tag)
            if pos >= 0:
                if not self.thinking:
                    output.append(self.pending[:pos])
                self.pending = self.pending[pos + len(tag):]
                self.thinking = not self.thinking
                self.seen = True
                continue
            # Retain only a possible partial tag across chunks.
            keep = next((n for n in range(min(len(tag) - 1, len(self.pending)), 0, -1)
                         if self.pending.endswith(tag[:n])), 0)
            end = len(self.pending) - keep
            if not self.thinking:
                output.append(self.pending[:end])
            self.pending = self.pending[end:]
            break
        return ''.join(output)

    def finish(self):
        # A partial opening tag might be the start of reasoning: discard it.
        self.pending = ''
