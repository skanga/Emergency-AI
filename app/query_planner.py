"""Deterministic retrieval vocabulary; topics are search hints, never diagnoses."""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata


def normalize(text):
    """Case/accent/punctuation normalization without translating unknown words."""
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+', text))


def normalize_language(language):
    """Normalize Kiwix ISO-639-3 and request locale codes to EN/PT/ES keys."""
    language = language.lower().replace('_', '-').split('-')[0]
    return {'eng': 'en', 'por': 'pt', 'spa': 'es'}.get(language, language)


def _contains(text, phrase):
    return f' {normalize(phrase)} ' in f' {text} '


@lru_cache(maxsize=1)
def _topics():
    return json.loads((Path(__file__).resolve().parent.parent / 'config/retrieval-topics.json').read_text())['topics']


@dataclass(frozen=True)
class QueryPlan:
    """Original question/language, inherited user terms, topic IDs, age/negation
    scope, up to two queries per source language, and untranslated fallback flag.
    """
    question: str
    request_language: str
    context_terms: tuple[str, ...]
    topics: tuple[str, ...]
    scope: dict
    queries_by_language: dict[str, tuple[str, ...]]
    limited_cross_language: bool


def _matches(text):
    return [name for name, spec in _topics().items()
            if any(all(_contains(text, word) for word in group) for group in spec['triggers'])]


def _age(text):
    numeric = re.search(r'\b(\d+)\s+(month|months|mes|meses|year|years|ano|anos)\b', text)
    if numeric:
        amount = int(numeric[1])
        months = amount if numeric[2] in {'month', 'months', 'mes', 'meses'} else amount * 12
        return 'infant' if months < 12 else 'child' if months < 216 else 'adult'
    for age, phrases in [('infant', ('infant', 'baby', 'bebe', 'lactente', 'month old', 'meses')), ('child', ('child', 'crianca', 'nino', 'year old')), ('adult', ('adult', 'adulto', 'adulta'))]:
        if any(_contains(text, phrase) and not any(_contains(text, prefix + ' ' + phrase) for prefix in ('not', 'not an', 'not a', 'no', 'nao', 'nao e', 'no es')) for phrase in phrases):
            return age
    return None


def plan_query(question, request_language='en', history=()):
    """Plan using at most three recent user turns. Current explicit topics and
    topic-change markers reset context; compatible follow-ups inherit user scope.
    Assistant messages never contribute vocabulary or patient facts.
    """
    request_language = normalize_language(request_language)
    current = normalize(question)
    user_turns = [normalize(m.get('content', '')) for m in (history or ())
                  if m.get('role') == 'user'][-3:]
    topics, negated, context = [], [], []
    age = None
    for turn in user_turns + [current]:
        turn_topics = _matches(turn)
        denied_topics = set()
        for name, spec in _topics().items():
            phrases = [p for group in spec['triggers'] if len(group) == 1 for p in group]
            if any(_contains(turn, prefix + ' ' + p) for p in phrases for prefix in ('not', 'no', 'nao', 'sem', 'sin')):
                denied_topics.add(name)
        positive_topics = [name for name in turn_topics if name not in denied_topics]
        equipment = any(_contains(turn, p) for p in ('camera', 'engine', 'motor'))
        # "Stroke" also describes engines. Specific medical symptoms disambiguate
        # that word; equipment itself does not invalidate an explicit emergency.
        if equipment and 'stroke' in positive_topics and not any(
                _contains(turn, p) for p in ('drooping face', 'slurred speech', 'avc', 'acidente vascular cerebral', 'accidente cerebrovascular')):
            positive_topics.remove('stroke')
        reset = any(_contains(turn, p) for p in ('new question', 'different topic', 'unrelated', 'nova pergunta', 'outra pergunta', 'otra pergunta', 'nuevo tema'))
        nonmedical = equipment and not positive_topics
        if nonmedical or reset or (positive_topics and topics and not set(positive_topics) & set(topics) and 'cpr' not in positive_topics):
            topics, negated, context, age = [], [], [], None
        if nonmedical:
            continue
        for name in positive_topics:
            if name not in topics:
                topics.append(name)
            if name in negated:
                negated.remove(name)
        for name in _topics():
            if name in denied_topics:
                if name not in negated:
                    negated.append(name)
                if name in topics:
                    topics.remove(name)
        age = _age(turn) or age
        if turn != current:
            context.append(turn)
    prior = ' '.join(context)
    # Prefer specific contamination over generic flooding.
    if 'water_chemical' in topics and 'flood' in topics:
        topics.remove('flood')
    if 'cpr' in topics:
        topics.remove('cpr')
        topics.insert(0, 'cpr')
    queries = {}
    if topics:
        for language in ('en', 'pt', 'es'):
            candidates = [_topics()[topic]['queries'][language][0] for topic in topics]
            if len(candidates) == 1:
                candidates = _topics()[topics[0]]['queries'][language]
            age_term = {'en': 'infant', 'pt': 'bebê', 'es': 'lactante'}[language] if age == 'infant' and any(t in topics for t in ('cpr', 'choking')) else ''
            queries[language] = tuple((q + ' ' + age_term).strip() for q in dict.fromkeys(candidates[:2]))
    else:
        queries[request_language] = (current,) if current else ()
    return QueryPlan(question, request_language, tuple(prior.split()), tuple(topics),
                     {'age_group': age, 'negated_facts': tuple(negated)}, queries, not bool(topics))
