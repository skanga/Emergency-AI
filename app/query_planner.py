"""Deterministic retrieval vocabulary; topics are search hints, never diagnoses."""

from __future__ import annotations

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
def _vocabulary():
    return json.loads((Path(__file__).resolve().parent.parent / 'config/retrieval-topics.json').read_text(encoding='utf-8'))


def _topics():
    return _vocabulary()['topics']


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
    context_turns: tuple[str, ...] = ()


def symptom_topics(text):
    """Match conjunctions of symptom alternatives, shared by routing and exclusions."""
    text = normalize(text)
    return {name for name, spec in _topics().items()
            if any(all(any(_contains(text, phrase) for phrase in alternatives) for alternatives in rule)
                   for rule in spec.get('symptoms', []))}


def matching_topics(text):
    """Recognize configured topic phrases, independently of search query wording."""
    text = normalize(text)
    symptoms = symptom_topics(text)
    return [name for name, spec in _topics().items()
            if name in symptoms or any(all(_contains(text, word) for word in group) for group in spec['triggers'])]


def topic_terms(topics):
    """Source concepts need not be identical to the two native search queries."""
    return tuple(dict.fromkeys(normalize(term) for topic in topics
                               for term in _topics()[topic].get('source_terms', [])
                               + [q for queries in _topics()[topic]['queries'].values() for q in queries]))


def has_topic_evidence(text, topics, question='', direct_title=''):
    """Require concrete context only for the question's applicable topic scope."""
    text, question = normalize(text), normalize(question)
    for topic in topics:
        spec = _topics()[topic]
        if spec.get('body_only_evidence') and direct_title in topic_terms([topic]):
            return True
        scope = spec.get('evidence_scope', [])
        if scope and not any(_contains(question, phrase) for phrase in scope):
            return True
        if all(any(_contains(text, phrase) for phrase in alternatives)
               for alternatives in spec.get('required_evidence', [])):
            return True
    return False


def _age(text):
    for word, number in {'eight': '8', 'oito': '8', 'ocho': '8', 'six': '6', 'seis': '6', 'ten': '10', 'dez': '10', 'diez': '10', 'two': '2', 'dois': '2', 'dos': '2'}.items():
        text = re.sub(r'\b' + word + r'\b', number, text)
    numeric = re.search(r'\b(\d+)\s+(month|months|mes|meses|year|years|ano|anos)\b', text)
    if numeric:
        amount = int(numeric[1])
        months = amount if numeric[2] in {'month', 'months', 'mes', 'meses'} else amount * 12
        return 'infant' if months < 12 else 'child' if months < 216 else 'adult'
    for age, phrases in [('neonatal', ('neonatal', 'neonate', 'newborn', 'recem nascido', 'recien nacido')), ('infant', ('infant', 'infants', 'baby', 'babies', 'bebe', 'bebes', 'lactente', 'lactante', 'month old', 'meses')), ('child', ('child', 'children', 'crianca', 'criancas', 'nino', 'ninos', 'nina', 'ninas', 'year old')), ('adult', ('adult', 'adults', 'adulto', 'adultos', 'adulta', 'adultas'))]:
        if any(_contains(text, phrase) and not any(_contains(text, prefix + ' ' + phrase) for prefix in ('not', 'not an', 'not a', 'no', 'nao', 'nao e', 'no es')) for phrase in phrases):
            return age
    return None


def _consciousness(text):
    """Use only stated responsiveness; breathing difficulty is not unconsciousness."""
    responsive = ('awake', 'conscious', 'responsive', 'alert', 'acordado', 'acordada', 'consciente', 'responde', 'despierto', 'despierta')
    unresponsive = ('unconscious', 'unresponsive', 'inconsciente', 'nao responde', 'no responde', 'not conscious', 'not responsive', 'will not respond', 'does not respond', 'will not wake up')
    if any(_contains(text, prefix + ' ' + phrase) for prefix in ('not', 'nao', 'no') for phrase in ('unconscious', 'unresponsive', 'inconsciente')):
        return 'responsive'
    if any(_contains(text, phrase) for phrase in unresponsive):
        return 'unresponsive'
    if any(_contains(text, phrase) for phrase in responsive):
        return 'responsive'
    return None


def plan_query(question, request_language='en', history=()):
    """Plan using at most three recent user turns. Current explicit topics and
    topic-change markers reset context; compatible follow-ups inherit user scope.
    Assistant messages never contribute vocabulary or patient facts.
    """
    request_language = normalize_language(request_language)
    current = normalize(question)
    user_turns = [m.get('content', '') for m in (history or ())
                  if m.get('role') == 'user'][-3:]
    topics, negated, context = [], [], []
    raw_context = []
    age = None
    consciousness = None
    focus = []
    for raw_turn in user_turns + [question]:
        turn = normalize(raw_turn)
        turn_topics = matching_topics(turn)
        denied_topics = set()
        for name, spec in _topics().items():
            phrases = [p for group in spec['triggers'] if len(group) == 1 for p in group]
            if any(_contains(turn, prefix + ' ' + p) for p in phrases for prefix in ('not', 'no', 'nao', 'sem', 'sin')):
                denied_topics.add(name)
        senses = [rule for rule in _vocabulary().get('non_emergency', [])
                  if any(all(_contains(turn, phrase) for phrase in group) for group in rule['groups'])]
        explicit_symptoms = symptom_topics(turn)
        excluded = {topic for rule in senses for topic in rule['exclude']} - explicit_symptoms
        # A device or recipe near a patient does not negate stated symptoms.
        if any(_contains(turn, p) for p in ('drooping face', 'slurred speech', 'avc', 'acidente vascular cerebral', 'accidente cerebrovascular')):
            excluded.discard('stroke')
        positive_topics = [name for name in turn_topics if name not in denied_topics and name not in excluded]
        focus = [phrase for rule in senses for phrase in rule['focus'] if _contains(turn, phrase)]
        equipment = any(_contains(turn, p) for p in ('camera', 'engine', 'motor'))
        # "Stroke" also describes engines. Specific medical symptoms disambiguate
        # that word; equipment itself does not invalidate an explicit emergency.
        if equipment and 'stroke' in positive_topics and 'stroke' not in explicit_symptoms and not any(
                _contains(turn, p) for p in ('drooping face', 'slurred speech', 'avc', 'acidente vascular cerebral', 'accidente cerebrovascular')):
            positive_topics.remove('stroke')
        reset = any(_contains(turn, p) for p in ('new question', 'different topic', 'different problem', 'unrelated', 'nova pergunta', 'outra pergunta', 'outro problema', 'otra pregunta', 'otro problema', 'nuevo tema'))
        nonmedical = (equipment or senses) and not positive_topics
        if nonmedical or reset or (positive_topics and topics and not set(positive_topics) & set(topics) and 'cpr' not in positive_topics):
            topics, negated, context, age = [], [], [], None
            consciousness = None
            raw_context = []
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
        consciousness = _consciousness(turn) or consciousness
        if turn != current:
            context.append(turn)
            raw_context.append(raw_turn)
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
                     {'age_group': age, 'consciousness': consciousness, 'negated_facts': tuple(negated), 'focus_terms': tuple(focus) if not topics else ()}, queries, not bool(topics), tuple(raw_context))
