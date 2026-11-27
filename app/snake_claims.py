"""Bounded snakebite source qualifiers; these do not select a clinical protocol."""
import re

BODY = r'\b(?:limb|leg|arm|wrist|membro|miembro|pierna|braco|brazo|muneca|punho)\b'
POSITIONS = {
    'elevation': r'\b(?:elevat\w*|elevad\w*|eleve|(?:raise|levante)(?= (?:the |o |el |la )?(?:bitten |mordido )?' + BODY + r'))\b',
    'vertical': r'\b(?:vertical position|posi(?:cion|cao) vertical)\b',
    'wrist_flexion': r'\b(?:flexed wrist|wrist flexed|(?:muneca|punho) flexionad\w*)\b',
}
POSITION = '|'.join(POSITIONS.values())


def positions(text):
    return {name for name, pattern in POSITIONS.items() if re.search(pattern, text)}


CLEANING = r'\b(?:wash\w*|clean\w*(?![a-z]| (?:water|cloth)\b)|lav(?:e|ar|a|ado|agem)\w*|limp(?:ie|iar|eza)\w*)\b'


def cleaning_scope_supported(claim, evidence):
    regions = r'\b(?:australi\w*|bra[sz]il\w*|philippin\w*|filipin\w*)\b'
    def region_set(text):
        return {('australia' if word.startswith('australi') else
                 'brazil' if word.startswith(('braz', 'bras')) else 'philippines')
                for word in re.findall(regions, text)}
    claimed, supplied = region_set(claim), region_set(evidence)
    if claimed != supplied:
        return False
    # An organization mentioned elsewhere in an article cannot lend attribution
    # to this instruction. Compare only the evidence unit containing the action.
    authorities = (r'\b(?:who|oms|world health organization)\b',
                   r'\b(?:red cross|cruz roja|cruz vermelha)\b')
    return all(not re.search(pattern, claim) or re.search(pattern, evidence)
               for pattern in authorities)


def efficacy_relations(text):
    """Keep the documented Crotalus conclusion separate from a cobra contrast."""
    found = set()
    if not re.search(r'\b(?:tourniquets?|torniquetes?|garrotes?)\b', text):
        return found
    for clause in re.split(r'\b(?:but|however|mas|pero)\b', text):
        if not re.search(r'\bcrotalus(?: durissus)?\b', clause):
            continue
        if not re.search(r'\b(?:in)?(?:effective|eficaz|eficazes|eficaces)|\bpositive results\b', clause):
            continue
        negative = bool(re.search(r'\b(?:ineffective|ineficaz\w*|ineficaces|not effective|nao (?:sao |e )?eficaz\w*|no (?:son |es )?eficaces)\b', clause))
        uncertain = bool(re.search(r'\b(?:no convincing evidence|no evidence|nao ha evidencias|no hay evidencia)\b', clause))
        # A stated exception reverses the preceding general ineffectiveness claim.
        if re.search(r'\b(?:except|exceto|salvo)\b.*\bcrotalus\b', clause):
            negative, uncertain = False, False
        found.add(('tourniquet', 'efficacy:crotalus', 'uncertain' if uncertain else negative))
    return found
