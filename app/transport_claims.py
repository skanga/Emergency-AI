"""Bounded transport actions and methods, including unsupported alternatives."""
import re
from .safety_patterns import conditions_conjoined

_DRAG = r'(?:drag(?:ging|ged)?|arrast\w*)'
PATTERN = (r'\b(?:carry|carried|carrying|carreg\w*|levem|lleven|llevar|cargu\w*|'
           + _DRAG + r'|wheelchairs?|cadeiras? de rodas|sillas? de ruedas|'
           r'support (?:(?:your|their|the person s) weight|you|them|the person))\b')
_METHODS = {
    'stretcher': r'\b(?:stretchers?|maca|camilla)\b',
    'chair': r'\b(?:chairs?|cadeiras?(?! de rodas)|sillas?(?! de ruedas))\b',
    'wheelchair': r'\b(?:wheelchairs?|cadeiras? de rodas|sillas? de ruedas)\b',
    'dragging': r'\b' + _DRAG + r'\b',
    'unspecified_support': r'\b(?:similar (?:support|aid|device)|any device|qualquer dispositivo|cualquier dispositivo)\b',
    'arms': r'\b(?:in (?:(?:their|your|his|her|the helper s) )?arms|nos bracos|en brazos)\b',
    'weight_support': r'\bsupport (?:(?:your|their|the person s) weight|you|them|the person)\b',
}


def negative_at(text, position):
    """Negation belongs to its clause, never an earlier unrelated warning."""
    prefix = re.split(r';|\b(?:but|however|pero|mas)\b', text[:position])[-1]
    return bool(re.search(r'\b(?:do not|don t|never|not|nao|no|nunca|rather than|instead of|em vez de|en vez de)\b[^;]{0,80}$', prefix))


def methods(text):
    """Only positive methods supply evidence for a positive carrying action."""
    return {name for name, pattern in _METHODS.items()
            for match in re.finditer(pattern, text)
            if not negative_at(text, match.start())}


def self_rescue_conditions(text):
    """Preserve necessity AND a known safe route across bounded paraphrases."""
    matches = [re.search(pattern, text) for pattern in (
        r'\b(?:only option|last option|last resort|unica opcao|unica opcion)\b',
        r'\b(?:known route|route (?:is )?known|rota conhecida|ruta conocida)\b',
        r'\b(?:safely|safe|com seguranca|con seguridad)\b',
    )]
    if not all(matches):
        return False
    if any(re.search(r'\b(?:not|never|nao|no|nunca) (?:\w+ ){0,2}$', text[:m.start()]) for m in matches):
        return False
    return all(conditions_conjoined(text, matches[0], other) for other in matches[1:])
