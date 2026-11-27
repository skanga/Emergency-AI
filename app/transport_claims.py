"""Bounded transport actions and methods, including unsupported alternatives."""
import re

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
