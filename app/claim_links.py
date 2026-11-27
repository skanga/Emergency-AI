"""Narrow citation links for repeated, unconditional snakebite prohibitions."""
import re

from .query_planner import normalize

CITATION = re.compile(r'\[S([1-9][0-9]*)\]')
_OBJECT = (r'(?:(?:a|an|the|um|un|una|o|el) )?(?:(?:tight|arterial) )*'
           r'(?:tourniquets?|torniquetes?|garrotes?|tight band(?:s|ages?)?|faixas? apertadas?|bandas? apretadas?)')
_BAN = re.compile(
    r'(?:do not|don t|never|nao|no|nunca) (?:(?:debe|debes|deben) )?'
    r'(?:use|apply|tie|apliqu(?:e|es|en|em)|aplicar|usar|amarre|utilice) '
    + _OBJECT + r'(?: (?:(?:or|ou|o|nem|ni) )?(?:(?:apply|use|tie) )?' + _OBJECT + r')*'
    r'(?: above the bite| acima da picada| por encima de la mordedura)?')


def plain_prohibition(text):
    """No conditions, explanations, quantities or extra actions may inherit a cite."""
    return bool(_BAN.fullmatch(normalize(CITATION.sub('', text))))


def insert_linked_citations(answer, claims):
    """Make verified links visible; offsets refer to the original model answer."""
    additions = {}
    for claim in claims:
        if claim.get('citation_binding') in ('repeated_prohibition', 'repeated_instruction') and claim['status'] == 'pattern_supported':
            additions.setdefault(claim['answer_span'][1], set()).update(claim['cited_ids'])
    for end, numbers in sorted(additions.items(), reverse=True):
        answer = answer[:end] + ' ' + ''.join(f'[S{n}]' for n in sorted(numbers, key=int)) + answer[end:]
    return answer


_PASSIVE_BAN = re.compile(_OBJECT + r' (?:is|are) (?:explicitly )?(?:contraindicated|prohibited|forbidden|advised against)')
_CARRY = re.compile(r'(?:have (?:helpers|people|your friends) carry (?:you|the person)|carry (?:you|the person))'
                    r'(?: on a (?:makeshift )?stretcher)?')


def repeated_instruction(text, rule):
    """Only bounded plain instructions can link; never explanations or exceptions."""
    clean = normalize(CITATION.sub('', text))
    if rule == 'snake_tourniquet':
        return plain_prohibition(text) or bool(_PASSIVE_BAN.fullmatch(clean))
    return rule == 'snake_transport' and bool(_CARRY.fullmatch(clean))
