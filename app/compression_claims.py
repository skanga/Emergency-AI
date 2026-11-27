"""Preserve explicit source restrictions on pressure-bandaging advice."""
import re

_BANDAGE = (r'(?:(?:compression|pressure(?: immobili[sz]ation)?|pressao|presion) '
            r'(?:bandages?|bandaging|bandagem|vendagem|vendaje|venda)|'
            r'(?:bandagem|vendagem|vendaje|venda) compress?iv\w*)')
PATTERN = (r'\b(?:(?:apply|use|wrap|apliqu(?:e|ese|es)|aplicar|coloque|aplica)\b.{0,45}\b'
           + _BANDAGE + r'|' + _BANDAGE
           + r' (?:can|may|should|must)(?: not)? be (?:applied|used))\b')
_ABSENCE = r'(?:without|no|sem|sin|ausencia de|(?:not|nao|no) (?:cause|causing|causam|provoca))'
_NO_SWELLING = r'\b' + _ABSENCE + r'(?: local)? (?:swelling|hinchazon|inchaco)\b'
_NEUROTOXIC = r'\bneurotoxic\w*\b'


def positive_swelling(text):
    for match in re.finditer(r'\b(?:swelling|hinchazon|inchaco)\b', text):
        prefix = text[:match.start()]
        if not re.search(r'\b' + _ABSENCE + r'(?: local)? $', prefix):
            return True
    return False


def restrictions_preserved(claim, evidence):
    """Restricted evidence cannot justify an unrestricted or inverted instruction."""
    if re.search(_NEUROTOXIC, evidence) and re.search(r'\b(?:non|not|nao|no) neurotoxic\w*\b', claim):
        return False
    for restriction in (_NEUROTOXIC, _NO_SWELLING):
        if re.search(restriction, evidence) and not re.search(restriction, claim):
            return False
    return True
