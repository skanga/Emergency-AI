"""Bounded transport-method extraction; matching is not clinical certification."""
import re

PATTERN = (r'\b(?:carry|carried|carrying|carreg\w*|levem|lleven|llevar|cargu\w*|'
           r'support (?:your|their|the person s) weight)\b')
_METHODS = {
    'stretcher': r'\b(?:stretchers?|maca|camilla)\b',
    'chair': r'\b(?:chairs?|cadeira|silla)\b',
    'arms': r'\b(?:in (?:(?:their|your|his|her|the helper s) )?arms|nos bracos|en brazos)\b',
    'weight_support': r'\bsupport (?:(?:your|their|the person s) weight|you|them|the person)\b',
}


def methods(text):
    """Exclude explicitly negated methods; a listed alternative still counts."""
    found = set()
    for name, pattern in _METHODS.items():
        for match in re.finditer(pattern, text):
            if not re.search(r'\b(?:not|never|nao|no|nunca) (?:in |on |em |en )?(?:(?:a|the|uma|una) )?$', text[:match.start()]):
                found.add(name)
    return found
