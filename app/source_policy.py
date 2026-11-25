"""Traceable source precedence, independent of retrieval scores or storage location.

Automatic detection is deliberately narrow: matching statements with conflicting
quantities. It does not recognize every paraphrase or clinical contradiction.
Only explicitly reviewed, version-bound rules establish precedence.
"""

from datetime import date
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path
import re

from .query_planner import normalize


def source_version(source):
    return (source.get('source_version') or source.get('archive_uuid') or source.get('document_hash')
            or hashlib.sha256(source.get('text', '').encode()).hexdigest())


def _quantities(text):
    # Compare an entire normalized statement, not unrelated doses sharing a unit.
    pattern = re.compile(r'(?<![\w.\-])(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|mg|mcg|liters?|litres?|drops?|minutes?|seconds?|compressions?)\b', re.I)
    found = {}
    for sentence in re.split(r'[\n;]|(?<=[.!?])\s+', text.casefold()):
        matches = list(pattern.finditer(sentence))
        if not matches:
            continue
        key = re.sub(r'\s+', ' ', pattern.sub(lambda m: '# ' + m['unit'], sentence)).strip()
        found.setdefault(key, set()).add(tuple((Decimal(m['number'].replace(',', '.')), m['unit']) for m in matches))
    return found


def _compatible(left, right):
    a, b = left.get('scope', {}), right.get('scope', {})
    if any(a[key] != b[key] for key in a.keys() & b.keys() if a[key] is not None and b[key] is not None):
        return False
    # Context outside the matching sentence can change applicability. Be
    # conservative when these recognizable qualifiers differ or are unknown.
    def qualifiers(source):
        raw = ' '.join(str(source.get(key, '')) for key in ('doc_title', 'title', 'section', 'heading_path', 'text'))
        text = normalize(raw)
        ages = set()
        for group, pattern in (
                ('infant', r'\b(infants?|bab(?:y|ies)|bebes?|lactantes?|lactentes?)\b'),
                ('child', r'\b(child(?:ren)?|criancas?|ninos?)\b'),
                ('adult', r'\b(adults?|adultos?)\b'),
                ('neonatal', r'\b(neonat(?:al|e)|newborn|recem nascido|recien nacido)\b')):
            if re.search(pattern, text):
                ages.add(group)
        # normalize() removes %, so inspect the original text for strengths.
        strengths = set(re.findall(r'\d+(?:[.,]\d+)?\s*%|\d+(?:[.,]\d+)?\s*(?:mg|mcg)\s*/\s*(?:ml|l)\b', raw, re.I))
        numeric_ages = set(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:years?|months?|weeks?|days?|anos?|mes(?:es)?|semanas?|dias?)\b', text))
        return ages, strengths, numeric_ages
    return qualifiers(left) == qualifiers(right)


def evaluate_conflicts(sources, topics=(), scope=None, policy=None):
    """Return durable conflict records; do not mutate passages or pick by score."""
    if policy is None:
        path = Path(__file__).resolve().parent.parent / 'config/source-policy.json'
        policy = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(policy, dict) or 'rules' not in policy
            or type(policy.get('version', 1)) is not int or policy.get('version', 1) != 1):
        raise ValueError('invalid_source_policy')
    rules = policy.get('rules', [])
    if not isinstance(rules, list):
        raise ValueError('invalid_source_policy')
    scope = scope or {}
    by_id = {s['id']: s for s in sources}
    conflicts = []
    reviewed_pairs = set()
    for rule in rules:
        if (not isinstance(rule, dict) or not all(isinstance(rule.get(k), str) and rule[k].strip() for k in ('id', 'topic', 'reviewer', 'reviewed_at', 'rationale'))
                or not isinstance(rule.get('sources'), dict) or len(rule['sources']) < 2
                or not isinstance(rule.get('scope', {}), dict)
                or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in rule['sources'].items())
                or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(rule['reviewed_at']))):
            raise ValueError('source_policy_requires_review_metadata')
        date.fromisoformat(rule['reviewed_at'])
        bindings = rule['sources']
        preferred = rule.get('preferred_source')
        if preferred is not None and (not isinstance(preferred, str) or preferred not in bindings):
            raise ValueError('source_policy_preferred_source_missing')
        if rule['topic'] not in topics or any(scope.get(k) != v for k, v in rule.get('scope', {}).items()):
            continue
        if not all(key in by_id and source_version(by_id[key]) == version for key, version in bindings.items()):
            continue
        for pair in itertools.combinations(sorted(bindings), 2):
            reviewed_pairs.add(pair)
        conflicts.append({'topic': rule['topic'], 'scope': dict(rule.get('scope', {})),
                          'disputed_point': rule.get('disputed_point', rule['rationale']),
                          'source_ids': sorted(bindings), 'versions': dict(bindings),
                          'detection_basis': 'reviewed_rule',
                          'resolution': 'reviewed_precedence' if preferred else 'unresolved',
                          'preferred_source': preferred, 'policy_rule_id': rule['id'],
                          'explanation': rule['rationale'], 'reviewer': rule['reviewer'],
                          'reviewed_at': rule['reviewed_at']})
    # Conflicting reviews cannot establish a single applicable precedence.
    for left, right in itertools.combinations(conflicts, 2):
        if (set(left['source_ids']) & set(right['source_ids'])
                and left.get('preferred_source') != right.get('preferred_source')):
            left['resolution'] = right['resolution'] = 'unresolved'
            left['explanation'] += ' Applicable reviewed rules disagree.'
            right['explanation'] += ' Applicable reviewed rules disagree.'
    quantities = {s['id']: _quantities(s.get('text', '')) for s in sources}
    for left, right in itertools.combinations(sources, 2):
        if tuple(sorted((left['id'], right['id']))) in reviewed_pairs:
            continue
        a, b = quantities[left['id']], quantities[right['id']]
        different = [key for key in a.keys() & b.keys() if a[key] != b[key]]
        # Scope extraction scans whole passages. Only do it when two matching
        # statements actually disagree; most evidence pairs share no statement.
        if not different or not _compatible(left, right):
            continue
        ids = sorted((left['id'], right['id']))
        conflicts.append({'topic': topics[0] if topics else 'unspecified', 'scope': dict(scope),
                          'disputed_point': 'Conflicting quantities in matching source statements.',
                          'source_ids': ids, 'versions': {s['id']: source_version(s) for s in (left, right)},
                          'detection_basis': 'matching_statement_quantities', 'resolution': 'unresolved',
                          'policy_rule_id': None,
                          'explanation': 'No applicable reviewed precedence rule resolves this disagreement.'})
    for record in conflicts:
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
        record['id'] = 'conflict-' + hashlib.sha256(payload).hexdigest()[:16]
    return conflicts
