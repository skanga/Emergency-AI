"""Shared bounded observations from compatible user turns, never model claims."""
import re
from .query_planner import normalize, _consciousness

_ABNORMAL = re.compile(r'\b(?:not breathing(?: normally)?|no breathing(?!\s+(?:trouble|difficult(?:y|ies)|problems?)\b)|only gasping|gasping|nao respira\w*(?: normalmente)?|sem respiracao|no respira\w*(?: normalmente)?)\b')
_NORMAL = re.compile(r'\b(?:breathing normally|normal breathing|respira\w* normalmente)\b')
_SWALLOW = re.compile(r'\b(?:able to swallow(?: safely)?|can swallow(?: safely)?|(?:consegue|puder|pode) engolir|capaz de engolir|(?:puede|pueda) tragar|capaz de tragar)\b')
_UNSAFE_SWALLOW = re.compile(r'\b(?:nao (?:e )?capaz de engolir|no (?:es )?capaz de tragar|not able to swallow|cannot swallow|can t swallow|unable to swallow|difficulty swallowing|swollen tongue|throat swelling|nao (?:consegue|puder|pode) engolir|dificuldade para engolir|lingua inchada|no (?:puede|pueda) tragar|dificultad para tragar|lengua hinchada)\b')
_CONDITIONAL = re.compile(r'\b(?:if|when|only if|se|quando|si|cuando)\b')


def _breathing(text):
    if any(not (m[0] in ('gasping', 'only gasping') and re.search(r'\b(?:not|no|nao)\s*$', text[:m.start()])) for m in _ABNORMAL.finditer(text)):
        return 'abnormal'
    if _NORMAL.search(text):
        return 'normal'
    return None


def _facts(plan):
    facts = {'consciousness': None, 'breathing': None, 'swallowing': None,
             'age_group': plan.scope.get('age_group')}
    # Planner context contains only compatible prior user turns, never assistant
    # assertions. Current explicit facts override those inherited facts.
    for text in (*plan.context_turns, plan.question):
        for sentence in re.split(r'[.!?\n]+', text):
            t = normalize(sentence)
            if _CONDITIONAL.search(t):
                continue  # A hypothetical condition is not a patient observation.
            facts['consciousness'] = _consciousness(t) or facts['consciousness']
            facts['breathing'] = _breathing(t) or facts['breathing']
            if _UNSAFE_SWALLOW.search(t):
                facts['swallowing'] = 'unsafe'
            elif _SWALLOW.search(t):
                facts['swallowing'] = 'safe'
    return facts



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
