"""Bounded causal and cross-condition support checks, not semantic certification."""
import hashlib
import re
from .query_planner import normalize
from .snake_claims import efficacy_relations
from .source_sections import scope_local_source

_SUBJECTS = {
    'tourniquet': r'\b(?:tourniquets?|torniquetes?|garrotes?|tight (?:arterial )?bands?)\b',
    'movement': r'\b(?:walking|movement|caminhar|movimento|caminar|movimiento)\b',
}
_EFFECTS = {
    'venom_spread': r'\b(?:accelerat\w*|aceler\w*)\b.{0,65}\b(?:venom|veneno)\b',
    'tissue_damage': r'\b(?:(?:caus\w*|provoc\w*|worsen\w*|empeor\w*|pior\w*)\b[^;.!?]{0,100}\b(?:tissue damage|danos? (?:graves )?(?:aos tecidos|ao membro)|danos? (?:tisular(?:es)?|tecidual|teciduais))|(?:danar|damage) (?:los )?(?:tejidos|tissues))\b',
    'nerve_injury': r'\bcaus\w*\b[^;.!?]{0,100}\bnerve injury\b',
    'limb_loss': r'\bcaus\w*\b[^;.!?]{0,100}\blimb loss\b',
    'necrosis': r'\bcaus\w*\b[^;.!?]{0,100}\bnecros\w*\b',
    'blood_flow': r'\b(?:cut(?:ting)? off|restrict\w*|restring\w*|cort\w*)\b.{0,35}\b(?:blood flow|circulacao(?: sanguinea)?|circulacion)\b',
}
_WARNINGS = {'vomiting': r'\b(?:vomiting|vomitos)\b',
             'sweating': r'\b(?:sweating|sudor|suor|sudorese)\b',
             'agitation': r'\b(?:agitation|agitacao|agitacion)\b'}
from .safety_patterns import _CITATION as _CITE


def subjects(text):
    return {name for name, pattern in _SUBJECTS.items() if re.search(pattern,text)}


def relations(text, antecedent=None):
    text=normalize(_CITE.sub('',text))
    found=efficacy_relations(text)
    for effect,pattern in _EFFECTS.items():
        for match in re.finditer(pattern,text):
            preceding=[(m.start(),name) for name,p in _SUBJECTS.items()
                       for m in re.finditer(p,text[:match.start()])]
            subject=max(preceding)[1] if preceding else None
            if subject is None and re.match(r'^(?:it|they|this|isso|isto|esto|ellos|essa pratica|esta pratica|esta practica)\b',text):
                subject=antecedent or 'unresolved'
            if subject:
                negative=bool(re.search(r'\b(?:not|never|cannot|nao|no|nunca)\s*$',text[:match.start()]))
                uncertain=bool(re.search(r'\b(?:not known|not proven|not shown|no evidence|uncertain|nao comprovad\w*|no demostrado)\b.{0,30}$',text[:match.start()]))
                found.add((subject,effect,'uncertain' if uncertain else negative))
    return found


def warning_details(text):
    clean=normalize(text)
    found={name for name,pattern in _WARNINGS.items() if re.search(pattern,clean)}
    return found if len(found)>=2 else set()


def check_explanations(answer,sources,plan,units):
    if 'snakebite' not in plan.topics:
        return [],[]
    by_n={str(s['n']):s for s in sources if not s.get('context_omitted')}
    issues,claims=[],[]
    previous_subject=None
    for raw,start,end in units:
        required=relations(raw,previous_subject)
        details=warning_details(raw)
        current=subjects(normalize(raw))
        previous_subject=next(iter(current)) if len(current)==1 else None
        for kind,expected in [('explanation',required),('condition_warning',details)]:
            if not expected:continue
            evidence=[]
            cited=list(dict.fromkeys(_CITE.findall(raw)))
            for n in cited:
                source=by_n.get(n)
                if not source:continue
                scoped=scope_local_source(source,plan)
                retained=scoped.get('retained_spans') if scoped is not source else None
                # Full source sentences preserve causal subject and polarity.
                for match in re.finditer(r'[^\n.!?]+(?:[.!?])?',source.get('text','')):
                    if retained and not any(a<=match.start() and match.end()<=b for a,b in retained):continue
                    actual=relations(match[0]) if kind=='explanation' else warning_details(match[0])
                    if not (kind == 'explanation' and any(item[0] == 'unresolved' for item in expected)) and expected.issubset(actual):
                        evidence.append({'source_n':source['n'],'span':[match.start(),match.end()],
                                         'text_sha256':hashlib.sha256(source['text'].encode()).hexdigest()})
                        break
            if not evidence:
                issues.append('explanation_not_supported_by_cited_passage' if kind=='explanation'
                              else 'condition_detail_not_supported_by_cited_passage')
            claims.append({'rule':kind,'claim_type':kind,'answer_span':[start,end],
                           'cited_ids':cited,'evidence':evidence,
                           'status':'pattern_supported' if evidence else 'blocked'})
    return issues,claims
