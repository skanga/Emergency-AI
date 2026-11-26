"""Small, versioned paraphrase catalog; integrity is not clinical certification.

Selection uses planner topics only as hints. Every emitted unit retains its own
prerequisites in its text. Runtime uses no network and no generator.
"""
from datetime import date
import hashlib
import json
import re
from pathlib import Path

from .query_planner import normalize_language
from .applicability import inapplicability_reason
from .patient_facts import _facts

CATALOG_PATH = Path(__file__).resolve().parent / 'data' / 'guidance.json'


def _hash(unit):
    payload = {key: value for key, value in unit.items() if key != 'content_hash'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def load_catalog(path=CATALOG_PATH):
    """Validate the complete artifact before returning any units; no partial load."""
    catalog = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(catalog, dict) or catalog.get('version') != 1 or not isinstance(catalog.get('units'), list):
        raise ValueError('invalid_guidance_catalog')
    seen = set()
    for unit in catalog['units']:
        if (not isinstance(unit, dict)
                or any(not isinstance(unit.get(key), str) or not unit[key].strip()
                       for key in ('id', 'topic', 'reference_title', 'reference_url',
                                   'reference_section', 'reference_checked_at', 'content_hash'))
                or unit['id'] in seen
                or not unit['reference_url'].startswith('https://')
                or not isinstance(unit.get('scope'), dict)
                or not isinstance(unit.get('prerequisites'), list)
                or not isinstance(unit.get('contraindications'), list)
                or not isinstance(unit.get('translations'), dict)
                or set(unit['translations']) != {'en', 'pt', 'es'}
                or any(not isinstance(text, str) or not text.strip()
                       for text in unit['translations'].values())
                or unit['content_hash'] != _hash(unit)):
            raise ValueError('invalid_guidance_unit')
        date.fromisoformat(unit['reference_checked_at'])
        seen.add(unit['id'])
    return catalog['units']


def _source(unit, lang):
    text = unit['translations'][lang]
    return {'id': f"guidance:{unit['id']}:{lang}:v1", 'kind': 'guidance',
            'guidance_unit': unit['id'], 'guidance_hash': unit['content_hash'],
            'doc_title': unit['reference_title'], 'section': unit['reference_section'],
            'text': text, 'url': unit['reference_url'], 'language': lang,
            'topic': unit['topic'], 'scope': dict(unit['scope']),
            'reference_checked_at': unit['reference_checked_at'],
            'source_version': unit['content_hash'],
            'document_hash': hashlib.sha256(text.encode()).hexdigest(),
            'provenance': 'Versioned source-backed paraphrase; reference checked, not clinical approval.',
            'prerequisites': list(unit['prerequisites']),
            'contraindications': list(unit['contraindications']),
            'additional_references': list(unit.get('additional_references', []))}


def guidance_sources(plan, lang):
    """Unnumbered candidates for ordinary evidence admission and conflict checks.

    Compatible user history is already bounded/reset by QueryPlan. Never inspect
    assistant turns. Unknown patient facts retain conditional alternatives.
    Failure to load the catalog returns no guidance, preserving retrieval paths.
    """
    lang = normalize_language(lang)
    if lang not in {'en', 'pt', 'es'}:
        return []
    try:
        catalog = load_catalog()
    except (OSError, ValueError, TypeError, KeyError):
        return []
    sources = []
    facts = _facts(plan)
    for unit in catalog:
        if 'safe swallowing' in unit['prerequisites'] and facts['swallowing'] == 'unsafe':
            continue
        if unit['topic'] not in plan.topics:
            continue
        scope = unit['scope']
        if any(plan.scope.get(key) is not None and plan.scope[key] != value
               for key, value in scope.items()):
            continue
        source = _source(unit, lang)
        if inapplicability_reason(source, plan) is None:
            sources.append(source)
    return sources


def fallback_answer(sources, lang, conflicts):
    """Compose only authentic, numbered catalog units admitted for this request.

    The caller is responsible for applicability/evidence admission and for
    displaying any used omitted sources BEFORE text citations. Omitted evidence
    is returned explicitly in fallback_evidence_ids; no draft-access claim is made.
    Unknown unresolved topics block all guidance conservatively. Topic-wide
    exclusion also prevents a different catalog ID from reviving disputed advice.
    """
    meta = {'status': 'unavailable', 'used_source_ids': [],
            'fallback_evidence_ids': [], 'coverage': 'catalog_units_only'}
    lang = normalize_language(lang)
    if lang not in {'en', 'pt', 'es'}:
        return '', meta
    if any(c.get('resolution') == 'policy_error' or c.get('detection_basis') == 'policy_error'
           for c in conflicts):
        meta['reason'] = 'policy_error'
        return '', meta
    blocked_ids, blocked_topics = set(), set()
    for conflict in conflicts:
        ids = set(conflict.get('source_ids', []))
        if conflict.get('resolution') == 'reviewed_precedence':
            blocked_ids.update(ids - {conflict.get('preferred_source')})
        else:
            blocked_ids.update(ids)
            topic = conflict.get('topic')
            if not topic or topic == 'unspecified':
                meta['reason'] = 'unresolved_conflict'
                return '', meta
            blocked_topics.add(topic)
    try:
        canonical = {_source(unit, lang)['id']: _source(unit, lang)
                     for unit in load_catalog()}
    except (OSError, ValueError, TypeError, KeyError):
        meta['reason'] = 'catalog_unavailable'
        return '', meta
    lines, used_numbers = [], set()
    for source in sources:
        if source.get('context_omitted'):
            source = dict(source, text=source.get('original_text'))
        expected = canonical.get(source.get('id'))
        number = source.get('n')
        if (expected is None or source['id'] in blocked_ids
                or expected['topic'] in blocked_topics
                or source['id'] in meta['used_source_ids']
                or type(number) is not int or number < 1 or number in used_numbers
                or any(source.get(key) != value for key, value in expected.items())):
            continue
        sentences = re.split(r"(?<=[.!?])\s+", expected["text"])
        lines.append(" ".join(f"{sentence[:-1]} [{number}]{sentence[-1]}"
                              if sentence.endswith((".", "!", "?"))
                              else f"{sentence} [{number}]" for sentence in sentences))
        used_numbers.add(number)
        meta['used_source_ids'].append(source['id'])
        if source.get('context_omitted') or source.get('context_included') is False:
            meta['fallback_evidence_ids'].append(source['id'])
    if lines:
        meta['status'] = 'composed'
    return '\n\n'.join(lines), meta
