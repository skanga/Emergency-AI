"""Conservative admission checks for complete first-aid evidence passages.

These checks identify known scope hazards, not medical truth or source authority.
They never edit instructions or grant precedence to one source over another.
"""
import re

from .query_planner import normalize


_ROUTE = re.compile(r'\b(iv|i v|intraven\w*|endoven\w*|intraosse\w*)\b')
_CLINICAL_ACTION = re.compile(r'\b(give|given|giving|administer\w*|inject\w*|insert\w*|insira|inserir|infus\w*|bolus|titrate\w*|establish|administ\w*|injete|inyect\w*)\b')
_INJECTION_ROUTE = re.compile(r'\b(im|sc|subcutan\w*|intramuscul\w*)\b')
_DOSE = re.compile(r'\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|ml|g|units|unidades)\b|\bd50\b')
_INVASIVE = re.compile(r'\b(intubat\w*|thoracotom\w*|thoracostom\w*|pericardiocentesis|reboa|craniectomy|thrombectomy|thrombolysis|neurosurg\w*|cesarean|caesarean|cesariana|cesarea|displace the uterus|push the uterus|uterus should be)\b')
_STOP_CPR = re.compile(r'\b(?:stop\w*|terminat\w*|cess\w*|interromp\w*|suspend\w*)\s+(?:the\s+)?(?:cpr|rcp|resuscitation|ressuscitacao|reanimacion)\b|\bpronounc\w*\s+(?:the\s+)?(?:person s\s+)?death\b')
_PASSIVE_STOP_CPR = re.compile(r'\b(?:cpr|rcp|resuscitation|ressuscitacao|reanimacion)\b.{0,45}\b(?:stopped|terminated|interrompida|suspendida)\b')
_CLINICAL_STOP = re.compile(r'\basystole\b|\bassistolia\b|\basistolia\b|\b\d+\s*(?:minutes?|minutos?)\b|\bpronounc\w*\b')
_ORAL = re.compile(r'\b(oral|by mouth|por boca|pela boca|15 15 rule)\b|\b(?:consum\w*|give|administer\w*)\b.{0,60}\b(?:carbohydrate|glucose|sugar)\b')
_ADULT = re.compile(r'\b(adults?|adultos?|adultas?)\b')
_COMPRESSIONS_ONLY = re.compile(r'\b(?:compressions only|only compressions|somente compressoes|solo compresiones)\b')


def _statements(text):
    # Keep conditional clauses at commas; semicolons can introduce a new action.
    for part in re.split(r'[\n;]+|(?<=[.!?])\s+', text):
        cleaned = normalize(part)
        if cleaned:
            yield cleaned


def _prohibition(statement):
    """A negative instruction is not permission to perform that action."""
    if re.search(r'\b(but|however|instead|mas|porem|pero|sin embargo)\b', statement):
        return False
    negative = re.search(r'\b(do not|never|nao|nunca|no (?=administr|inyect|insert|intente|dar|de ))\b', statement)
    if not negative:
        return False
    # A conjunction can introduce a second, affirmative instruction.
    if re.search(r'\b(and|then|e|y|entao|luego)\b', statement[negative.end():]):
        return False
    prefix = statement[:negative.start()].strip()
    return not prefix or (bool(re.match(r'^(if|when|for|se|quando|si|cuando)\b', prefix))
                          and not _CLINICAL_ACTION.search(prefix))


def inapplicability_reason(source, plan):
    if 'text' not in source:
        return None  # Candidate metadata is not a fetched procedure.
    text = source['text']
    body = normalize(text)
    statements = list(_statements(text))
    for statement in statements:
        if _prohibition(statement):
            continue
        if (_STOP_CPR.search(statement) or _PASSIVE_STOP_CPR.search(statement)) and _CLINICAL_STOP.search(statement):
            return 'clinical_resuscitation_decision'
        if _INVASIVE.search(statement):
            return 'invasive_procedure'
        if _CLINICAL_ACTION.search(statement) and re.search(r'\b(?:acls drugs|activated charcoal|octreotide)\b', statement):
            return 'clinical_drug_administration'
        if _DOSE.search(statement) and re.search(r'\b(?:bolus|drip|infusion)\b', statement):
            return 'clinical_infusion_dosing'
        if _INJECTION_ROUTE.search(statement) and _DOSE.search(statement):
            return 'clinical_injection_dosing'
        if _ROUTE.search(statement) and (_CLINICAL_ACTION.search(statement) or _DOSE.search(statement)):
            return 'clinical_drug_administration'
    if plan.scope.get('age_group') == 'infant':
        # A general heading can hide adult instructions inside a mixed-age guide.
        if _ADULT.search(body) and (_COMPRESSIONS_ONLY.search(body) or 'abdominal thrust' in body):
            return 'mixed_adult_infant_procedure'
    if plan.scope.get('consciousness') == 'unresponsive':
        for statement in statements:
            if not _prohibition(statement) and _ORAL.search(statement):
                return 'oral_treatment_for_unresponsive_patient'
    return None
