"""Shared bounded citation and clinical-safety vocabulary.

Inputs to clinical helpers are normalized text. Observation and source-evidence
patterns deliberately retain their existing, different scopes. This module does
not decide whether an entire answer can be released.
"""
import re
from .query_planner import _consciousness

_CITATION = re.compile(r'\[S([1-9][0-9]*)\]')
_REFERENCE = re.compile(r'\[(?:[Ss][^\]\n]*|\^?\d[^\]\n]*)\]')
_FOOTNOTE = re.compile(r'\[(\d+(?:\s*[,–-]\s*\d+)*)\]')
_OBSERVED_ABNORMAL = re.compile(r'\b(?:not breathing(?: normally)?|no breathing(?!\s+(?:trouble|difficult(?:y|ies)|problems?)\b)|only gasping|gasping|breathing abnormally|nao respira\w*(?: normalmente)?|sem respiracao|no respira\w*(?: normalmente)?)\b')
_NORMAL = re.compile(r'\b(?:breathing normally|normal breathing|respira\w* normalmente)\b')
_SWALLOW = re.compile(r'\b(?:able to swallow(?: safely)?|can swallow(?: safely)?|(?:consegue|puder|pode) engolir|capaz de engolir|(?:puede|pueda) tragar|capaz de tragar)\b')
_UNSAFE_SWALLOW = re.compile(r'\b(?:nao (?:e )?capaz de engolir|no (?:es )?capaz de tragar|not able to swallow|cannot swallow|can t swallow|unable to swallow|difficulty swallowing|swollen tongue|throat swelling|nao (?:consegue|puder|pode) engolir|dificuldade para engolir|lingua inchada|no (?:puede|pueda) tragar|dificultad para tragar|lengua hinchada)\b')
_CONDITIONAL = re.compile(r'\b(?:if|when|only if|se|quando|si|cuando)\b')
_ACTION_NEGATIVE = re.compile(r'\b(?:do not|don t|never|must not|nao|nunca|no)\s+(?:(?:attempt to|try to|tente|intente)\s+)?$')
_CLAIM_NEGATIVE = re.compile(r'\b(?:do not|don t|never|avoid|must not|should not|cannot|can t|nao|nunca|evite|no|evitar|nem|ni|nor)\s+(?:(?:attempt to|try to|tente|intente|intentes|intenten)\s+)?$')
_UNRESPONSIVE = r'\b(?:unresponsive|unconscious|inconsciente|nao responde|no responde)\b'
_SOURCE_ABNORMAL = r'\b(?:not breathing(?: normally)?|no breathing(?! (?:trouble|difficulty|problems?))|(?:only )?gasping|breathing abnormally|nao respir\w*|no respir\w*)\b'
_RESPONSIVE = r'\b(?:awake|conscious|responsive|alert|acordad[oa]|consciente|despiert[oa])\b'
_NOT_AWAKE = r'\b(?:not|nao|no) (?:awake|conscious|responsive|alert|acordad[oa]|consciente|despiert[oa])\b'


def _breathing(text):
    if any(not (m[0] in ('gasping', 'only gasping', 'breathing abnormally') and re.search(r'\b(?:not|no|nao)\s*$', text[:m.start()])) for m in _OBSERVED_ABNORMAL.finditer(text)):
        return 'abnormal'
    if _NORMAL.search(text):
        return 'normal'
    return None


def cpr_prerequisite_scope(text):
    """A directly attached 'CPR only if' is mandatory; another action cannot lend it."""
    for original,replacement in (
        ('nao responder','nao responde'), ('no responda','no responde'),
        ('nao tiver respiracao normal','nao respira normalmente'),
        ('no tenga respiracion normal','no respira normalmente'),
    ):
        text=re.sub(r'\b'+original+r'\b',replacement,text)
    attached=re.search(r'\b(?:cpr|rcp)(?: reanimacao cardiopulmonar| reanimacion cardiopulmonar)? '
                       r'(?:only if|apenas se|somente se|solo si)\b',text)
    return 'if '+text[attached.end():].strip() if attached else text


def _negative_action(text, match, pattern=_ACTION_NEGATIVE):
    prefix = text[:match.start()]
    return bool(pattern.search(prefix))


def _cpr_condition(text, facts):
    text = cpr_prerequisite_scope(text)
    if not _CONDITIONAL.search(text):
        return False
    state_value = _consciousness(text) or facts['consciousness']
    breath_value = _breathing(text) or facts['breathing']
    if state_value != 'unresponsive' or breath_value != 'abnormal':
        return False
    state = re.search(_UNRESPONSIVE, text)
    breath = _OBSERVED_ABNORMAL.search(text)
    if state and breath:
        if not conditions_conjoined(text, state, breath):
            return False
    return True


def _negative_swallow(text):
    return _matches(r'\b(?:not|never|nao|no|nunca) (?:able to swallow|can swallow|consegue engolir|capaz de engolir|puede tragar|capaz de tragar)\b|\b(?:cannot swallow|unable to swallow|can t swallow)\b', text)


def _source_conditions(name, text):
    """Evidence for CPR/oral therapy must carry prerequisites, not just a verb."""
    if name == 'cpr':
        text = cpr_prerequisite_scope(text)
        state, breath = re.search(_UNRESPONSIVE, text), re.search(_SOURCE_ABNORMAL, text)
        if (not state or not breath or _matches(r'\b(?:not|never|nao|no|nunca)\s+' + _UNRESPONSIVE, text)
                or re.search(r'\b(?:not|no|never) (?:gasping|breathing abnormally)\b', text)):
            return False
        return conditions_conjoined(text, state, breath)
    if name in ('oral', 'oral_adjunct'):
        state = re.search(_RESPONSIVE, text)
        swallow = re.search(_SWALLOW, text)
        if not state or not swallow or _consciousness(text) != 'responsive' or _matches(_NOT_AWAKE, text) or _negative_swallow(text) or _UNSAFE_SWALLOW.search(text):
            return False
        return conditions_conjoined(text, state, swallow)
    return True


def _swallowing(text):
    if _negative_swallow(text) or _UNSAFE_SWALLOW.search(text):
        return 'unsafe'
    if _matches(_SWALLOW, text):
        return 'safe'
    return None


def _matches(pattern, text):
    return bool(re.search(pattern, text))


def conditions_conjoined(text, first, second):
    """Reject alternative prerequisites; both condition matches must be present."""
    if not first or not second:
        return False
    between = text[min(first.end(), second.end()):max(first.start(), second.start())]
    return not re.search(r"\b(?:or|ou|o)\b", between)
