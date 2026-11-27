"""Select complete labelled condition blocks without editing the local guide."""
import hashlib
import re
from .query_planner import normalize

_OTHER_CONDITION = re.compile(r'^(?:scorpion|escorpiao|escorpion|brown recluse spider|aranha marrom|arana reclusa)\b')
_OTHER_REQUEST = re.compile(r'\b(?:scorpions?|escorpiao|escorpion|alacran|spiders?|aranha\w*|arana\w*|loxosceles)\b')


def scope_local_source(source, plan):
    if source.get('kind') != 'kit' or 'snakebite' not in plan.topics:
        return source
    request = normalize(' '.join((*plan.context_turns, plan.question)))
    if any(not re.search(r'\b(?:not|no|nao|without|sin|sem) (?:(?:a|an|um|uma|un|una) )?$', request[:m.start()])
           for m in _OTHER_REQUEST.finditer(request)):
        return source
    text = source.get('text', '')
    retained = []
    for block in re.finditer(r'[^\n](?:[\s\S]*?)(?:\n\s*\n|\Z)', text):
        if not _OTHER_CONDITION.search(normalize(block[0])):
            retained.append((block.start(), block.end()))
    selected = ''.join(text[start:end] for start,end in retained).strip()
    if not selected or selected == text.strip():
        return source
    return dict(source, id=source['id']+':scope-snakebite', text=selected,
                parent_source_id=source['id'], parent_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                retained_spans=[list(span) for span in retained],
                passage_sha256=hashlib.sha256(selected.encode()).hexdigest(),
                scope_selection='Complete labelled scorpion/spider blocks excluded for snakebite-only request')
