"""Bounded action/evidence checks. Matching is not general semantic entailment.

Each recognized instruction is checked against its own cited passage, not the
retrieval bag. Diagnostics identify rules and source spans, never rejected prose.
"""
from dataclasses import dataclass
import hashlib
import re

from .query_planner import normalize, _consciousness, _age
from .patient_facts import _breathing, _facts, _UNSAFE_SWALLOW

_CITE = re.compile(r'\[S([1-9][0-9]*)\]')
_NEGATIVE = re.compile(r'\b(?:do not|don t|never|avoid|must not|should not|cannot|can t|nao|nunca|evite|no|evitar)\s+(?:(?:attempt to|try to|tente|intente|intentes|intenten)\s+)?$')
_FIRMLY = r'\b(?:firmly|tightly|strongly|firmemente|fortemente|fuertemente)\b'
_STUCK = r'\b(?:stuck|adher\w*|grudad\w*|pegad\w*)\b'
_EXCEPT = r'\b(?:except|unless|leave|only if not|do not|don t|not remove|but not|nao|no|exceto|salvo|deixe|deje)\b'
_UNRESPONSIVE = r'\b(?:unresponsive|unconscious|inconsciente|nao responde|no responde)\b'
_ABNORMAL = r'\b(?:not breathing(?: normally)?|no breathing(?! (?:trouble|difficulty|problems?))|only gasping|nao respir\w*|no respir\w*)\b'
_SWALLOW = r'\b(?:able to swallow(?: safely)?|can swallow(?: safely)?|consegue engolir|puede tragar)\b'
_SAFE = r'\b(?:if safe|if it is safe|only if safe|se for seguro|se for seguro faze lo|si es seguro)\b'
_DEVICE = r'\b(?:epipen|jext|auvi q|anapen|emerade)\b'
_NOT_AWAKE = r'\b(?:not|nao|no) (?:awake|conscious|responsive|alert|acordad[oa]|consciente|despiert[oa])\b'


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: str
    topics: tuple = ()


# Object-specific verbs keep an unrelated "give" from turning a prohibition
# elsewhere in the sentence into a positive instruction.
RULES = (
    Rule('cpr_continuation', r'\b(?:continue|keep going)\b.{0,45}\b(?:until|ate|hasta que)\b', ('cpr',)),
    Rule('embedded_object', r'\b(?:remove|pull out|retire|remova|quite|extraiga)\b.{0,45}\b(?:embedded objects?|foreign objects?|objetos? (?:encravad\w*|incrustad\w*|cravad\w*|empalad\w*))\b', ('bleeding',)),
    Rule('generator_shutdown', r'\b(?:turn off|shut off|switch off|desligue|desligar|apague|apagar)\b.{0,35}\b(?:generator\w*|gerador\w*|generador\w*|equipment|equipamento|equipo)\b', ('carbon_monoxide',)),
    Rule('generator_reentry', r'\b(?:re enter|(?:return|go back|volte|voltar|retorne|regrese|volver)(?= (?:to|inside|into|a|ao|al|para|adentro|dentro)\b))\b', ('carbon_monoxide',)),
    Rule('generator_indoor', r'\b(?:use[ds]?|using|run|operate|utilize|usar|utilice|use|opere)\b.{0,110}\b(?:indoors|inside|garage\w*|garagem|garaje|interior|dentro)\b', ('carbon_monoxide',)),
    Rule('food_sensory', r'\b(?:judge|assess|re evaluate|evaluate|determine|rely|avalie|julgue|avalie novamente|confie|evalue|juzgue|confie)\b.{0,80}\b(?:appearance|smell|taste|aparencia|cheiro|sabor|aspecto|olor)\b|\b(?:eat|coma|consuma)\b.{0,35}\b(?:if|se|si)\b.{0,35}\b(?:smell\w*|cheiro|olor)\b', ('food_safety',)),
    Rule('burn_clothing', r'\b(?:remove|take off|separate|peel off|pull off|retire|retira|retirar|remova|remover|quite|quita|quitar|tire|tirar|separe|separar)\b.{0,65}\b(?:clothing|clothes|roupa\w*|ropa\w*)\b', ('burn',)),
    Rule('burn_jewelry_delay', r'\b(?:keep|leave|mantenha|deixe|manten|mantenga|deje|deja)\b.{0,50}\b(?:jewelry|jewellery|rings?|joias?|aneis|joyas?|anillos?)\b', ('burn',)),
    Rule('burn_cooling', r'\b(?:cool|run|hold|resfrie|arrefeca|enfrie|enfriar)\b.{0,90}\b(?:water|agua)\b', ('burn',)),
    Rule('immersion', r'\b(?:immerse|immersion|submerge|mergulh\w*|imersao|sumerj\w*|inmersion|sumerg\w*)\b', ('heatstroke',)),
    Rule('snake_compression', r'\b(?:apply|use|wrap|aplique|use|coloque|aplica)\b.{0,45}\b(?:compression|pressure|compress\w*|pressao|presion)\b.{0,35}\b(?:bandage|bandaging|bandagem|vendagem|vendaje|venda)\b', ('snakebite',)),
    Rule('injector_hold', r'\b(?:hold|keep|mantenha|segure|mantenga|sujete)\b.{0,65}\b(?:seconds?|segundos?)\b', ('anaphylaxis',)),
    Rule('flood_wait', r'\b(?:wait|stay|remain|espere|permaneca|quedese|permanezca)\b.{0,85}\b(?:water|vehicle|car|inside|recede|agua|veiculo|carro|vehiculo|dentro)\b', ('flood',)),
    Rule('fire_cover', r'\b(?:cover|smother|slide|cubra|abafe|tape|deslice|cobrir)\b', ('fire', 'grease_fire')),
    Rule('extinguisher', r'\b(?:use|using|apply|utilize|usar|utilice)\b.{0,55}\b(?:extinguisher|extintor)\b', ('fire', 'grease_fire')),
    Rule('cpr', r'\b(?:(?:start|begin|perform|give|initiate|continue|do(?= (?:cpr|rcp|chest compressions))|inicie|comece|faca|realize|comience|inicia|haga|realizar)\s+(?:\w+\s+){0,3}(?:cpr|rcp|chest compressions|compressoes toracicas|compresiones toracicas)|(?:cpr|rcp) (?:now|immediately|agora|ahora))\b'),
    Rule('oral', r'\b(?:give|offer|take|eat|drink|administer|dar|de|ofereca|tome|beba|coma|dele|administre)\b.{0,60}\b(?:glucose|sugar|juice|honey|food|drink|anything by mouth|oral|antihistamine\w*|tablet\w*|glicose|acucar|suco|mel|comprimido\w*|alimento\w*|bebida\w*|glucosa|azucar|jugo|miel|pastilla\w*|antihistaminico\w*)\b'),
    Rule('oral_adjunct', r'\b(?:consider\w*|adjunct|adjuvante|complemento|complementario)\b', ('anaphylaxis',)),
    Rule('water_chemical', r'\b(?:boil\w*|disinfect\w*|ferv\w*|desinfet\w*|herv\w*|desinfect\w*)\b', ('water_chemical',)),
    Rule('injector', r'\b(?:use|inject|administer|give|apply|aplique|administre|injete|inyecte|utilice)\b.{0,70}\b(?:epinephrine|adrenaline|auto injector|epipen|jext|anapen|adrenalina|epinefrina|autoinjetor|autoinyector)\b', ('anaphylaxis',)),
)


def _has(pattern, text):
    return bool(re.search(pattern, text))


def _units(text):
    """Split sentence/list boundaries, retaining an immediately trailing citation."""
    for match in re.finditer(r'(?:[^\n.!?]|(?<=\d)\.(?=\d))+(?:[.!?](?:[ \t]*\[S\d+\])*)?', text):
        value = match[0].strip()
        if value:
            yield value, match.start(), match.end()


def _polarity(rule, text, match):
    if rule.name == 'generator_shutdown' and _has(
            r'\b(?:do not|never|nao|no|nunca) (?:return|go back|volte|voltar|retorne|regrese|volver) (?:to|para) $', text[:match.start()]):
        return False
    if rule.name == 'generator_indoor':
        return not bool(re.search(r'\b(?:never|not|nao|no|nunca)(?: be| ser)? $', text[:match.start()]))
    if rule.name == 'water_chemical':
        # Preserve punctuation boundaries for this rule. An unrelated negative
        # instruction (such as 'do not worry') is not a disinfection claim.
        start = text.rfind(';', 0, match.start()) + 1
        end = text.find(';', match.end())
        clause = text[start:end if end >= 0 else len(text)]
        direct_prohibition = bool(_NEGATIVE.search(text[start:match.start()]))
        unsafe_result = _has(
            r'\b(?:not|cannot|can t|won t|never|nao|no|nunca|incapaz)\b'
            r'.{0,35}\b(?:make|made|remove|remov\w*|torn\w*|vuelv\w*|elimin\w*|safe|segur\w*)\b', clause)
        return not (direct_prohibition or unsafe_result)
    return not bool(_NEGATIVE.search(text[:match.start()]))


def _negative_swallow(text):
    return _has(r'\b(?:not|never|nao|no|nunca) (?:able to swallow|can swallow|consegue engolir|puede tragar)\b|\b(?:cannot swallow|unable to swallow|can t swallow)\b', text)


def _negative_prerequisite(text):
    # These are explicit reversals of the bounded extinguisher prerequisites.
    return _has(r'\b(?:not|never|no|nao|nunca|without|sem|sin)\s+(?:\w+\s+){0,2}'
                r'(?:suitable|rated|appropriate|trained|training|escape|exit|small|contained|'
                r'adequad\w*|apropriad\w*|treinad\w*|treinamento|capacitado|saida|salida|pequen\w*|contido|confinado)\b', text)


def _condition_issue(name, text, question, positive=True):
    if name == 'generator_indoor':
        # 'With or without ventilation' keeps the ban unconditional.
        exception_text = re.sub(r'\b(?:with or without|com ou sem|con o sin)\b', '', text)
        exception_text = re.sub(r'\b(?:even if|mesmo se|incluso si)\b', '', exception_text)
        if positive or _has(r'\b(?:unless|without|except|if|when|a menos que|sem|sin|exceto|salvo|se|si|quando|cuando)\b', exception_text):
            return 'generator_indoor_use_unsafe'
    if name == 'cpr_continuation' and positive:
        # A valid stopping branch cannot authorize a different arrival branch.
        for branch in text.split(';'):
            for arrival in re.finditer(r'\b(?:arrives?|chegar|chegue|llegue|lleguen)\b', branch):
                if not _has(
                        r'^ (?:and (?:begins? care|takes? over)|e (?:assuma|assumir)|y (?:se haga cargo|comience la atencion))\b',
                        branch[arrival.end():]):
                    return 'cpr_arrival_stop_unsafe'
    if name == 'embedded_object':
        # The prohibition cannot be weakened by an invented removal exception.
        suffix = re.split(r'\b(?:embedded objects?|foreign objects?|objetos? (?:encravad\w*|incrustad\w*|cravad\w*|empalad\w*))\b', text, maxsplit=1)[-1]
        suffix = re.sub(r'\b(?:even if|mesmo se|incluso si)\b', '', suffix)
        if positive or _has(r'\b(?:unless|except|if|when|a menos que|exceto|salvo|se|si|quando|cuando)\b', suffix):
            return 'embedded_object_removal_unsafe'
    if name == 'generator_shutdown' and positive:
        # No local shutdown procedure is established during suspected exposure.
        return 'generator_shutdown_condition_missing'
    if name == 'generator_reentry' and not positive and _has(
            r'\b(?:unless|except|a menos que|exceto|salvo)\b', text):
        return 'generator_reentry_condition_missing'
    clearance_text = text
    if name == 'generator_reentry' and not positive:
        for original, replacement in (('until', 'only after'), ('ate', 'somente apos'),
                                      ('hasta que', 'solo despues de que')):
            clearance_text = re.sub(r'\b' + original + r'\b', replacement, clearance_text)
    if name == 'generator_reentry' and (positive or _has(
            r'\b(?:if|when|until|se|quando|ate|si|cuando|hasta)\b', text)) and (
            _has(r'\b(?:or|ou|o si|o cuando)\b', text) or not _has(
            r'\b(?:(?:re enter|return to|go back to) (?:the )?(?:garage|area|building|house) '
            r'only after trained personnel declare the area safe|'
            r'(?:volte|retorne) (?:a|ao) (?:garagem|local) '
            r'somente apos profissionais treinados liberarem o local|'
            r'regrese (?:al garaje|a la zona) '
            r'solo despues de que profesionales capacitados declaren segura la zona)\b', clearance_text)):
        return 'generator_reentry_condition_missing'
    if name == 'food_sensory' and positive:
        return 'food_sensory_safety_unsupported'
    if not positive:
        return None
    if name == 'burn_jewelry_delay' and _has(
            r'\b(?:until|ate|hasta que)\b.{0,45}\b(?:swell\w*|incha\w*|hinch\w*)\b', text):
        return 'burn_jewelry_delay_unsafe'
    if name == 'burn_clothing' and (_has(_FIRMLY + r'\s+' + _STUCK + '|' + _STUCK + r'\s+' + _FIRMLY, text)
            or not _has(_EXCEPT + r'(?:(?!\b(?:but|mas|pero|and|e|y)\b).){0,65}' + _STUCK, text)
            or _has(r'\b(?:except|exceto|salvo)\b.{0,40}\b(?:not|nao|no)\s+' + _STUCK, text)):
        return 'burn_clothing_condition_missing'
    if name == 'immersion' and not (
            _has(r'\b(?:head|face|cabeca|rosto|cabeza|cara)\b (?:stays |kept |is |sempre |siempre )?(?:above|out of|fora|acima|fuera|encima)\b', text)
            and _has(r'\b(?:helper|someone|monitor\w*|assist\w*|ajud\w*|vigie|vigile|outra pessoa|otra persona)\b', text)):
        return 'immersion_airway_condition_missing'
    if name == 'snake_compression' and (not _has(r'\b(?:in australia|na australia|en australia)\b', question)
            or _has(r'\b(?:not|nao|no) (?:\w+ )?(?:in|na|en) australia\b', question)):
        return 'snake_compression_scope_missing'
    if name == 'injector_hold' and not _has(_DEVICE, question):
        return 'injector_device_scope_missing'
    if name == 'flood_wait' and not (
            _has(r'\b(?:rising|rises|subindo|subir|sube|subiendo)\b', text)
            and _has(r'\b(?:inside|dentro|interior)\b', text)
            and _has(r'\b(?:get|climb|go|seek refuge|procure abrigo|refugiese|suba|subir|subase)\b.{0,25}\b(?:roof|teto|techo)\b', text)
            and not _has(r'\b(?:not|never|nao|no|nunca) (?:get|climb|go|seek|suba|subir|procure|refugiese)\b.{0,35}\b(?:roof|teto|techo)\b', text)):
        return 'flood_entrapment_condition_missing'
    if name == 'fire_cover':
        if _has(r'\b(?:foil|aluminio|paper|towel|papel|toalha|pano|trapo)\b', text) or not _has(r'\b(?:lid|baking sheet|cookie sheet|tampa|tapa|assadeira|bandeja)\b', text):
            return 'grease_fire_equipment_unsupported'
        if not _has(_SAFE, text):
            return 'fire_approach_condition_missing'
    if name == 'extinguisher' and (_negative_prerequisite(text) or not all((
            _has(r'\b(?:rated|suitable|appropriate|adequad\w*|apropriad\w*|apto)\b', text),
            _has(r'\b(?:cooking oil|grease|oleo|gordura|aceite|grasa)\b', text),
            _has(r'\b(?:train\w*|treinad\w*|treinamento|capacitado|sabe usar)\b', text),
            _has(r'\b(?:escape|exit|saida|salida)\b', text),
            _has(r'\b(?:small|contained|pequen\w*|contido|confinado)\b', text)))):
        return 'extinguisher_conditions_missing'
    if name == 'oral_adjunct' and not (_consciousness(text) == 'responsive' and _has(_SWALLOW, text)):
        return 'oral_intake_prerequisites_missing'
    if name in ('oral', 'oral_adjunct') and (_has(_NOT_AWAKE, text) or _negative_swallow(text)):
        return 'oral_intake_prerequisites_missing'
    return None


def _source_conditions(name, text):
    """Evidence for CPR/oral therapy must carry prerequisites, not just a verb."""
    if name == 'cpr':
        state, breath = re.search(_UNRESPONSIVE, text), re.search(_ABNORMAL, text)
        if not state or not breath or _has(r'\b(?:not|never|nao|no|nunca)\s+' + _UNRESPONSIVE, text):
            return False
        between = text[min(state.end(), breath.end()):max(state.start(), breath.start())]
        return not _has(r'\b(?:or|ou|o)\b', between)
    if name in ('oral', 'oral_adjunct'):
        state = re.search(r'\b(?:awake|conscious|responsive|alert|acordad[oa]|consciente|despiert[oa])\b', text)
        swallow = re.search(_SWALLOW, text)
        if not state or not swallow or _consciousness(text) != 'responsive' or _has(_NOT_AWAKE, text) or _negative_swallow(text):
            return False
        between = text[min(state.end(), swallow.end()):max(state.start(), swallow.start())]
        return not _has(r'\b(?:or|ou|o)\b', between)
    return True


def _oral_objects(text):
    groups = {
        'carbohydrate':r'\b(?:glucose|sugar|juice|honey|glicose|acucar|suco|mel|glucosa|azucar|jugo|miel)\b',
        'antihistamine':r'\b(?:antihistamine\w*|antihistaminico\w*)\b',
    }
    return {name for name, pattern in groups.items() if _has(pattern, text)}


def _swallowing(text):
    if _negative_swallow(text) or _UNSAFE_SWALLOW.search(text):
        return 'unsafe'
    if _has(_SWALLOW, text):
        return 'safe'
    return None


def _claim_text(text, name):
    if name == 'cpr_continuation':
        return '; '.join(normalize(part) for part in re.split(r'[;\n]', text))
    if name == 'water_chemical':
        return '; '.join(normalize(part) for part in re.split(r'[;]', text))
    return normalize(text)


def _negative_scope_supported(name, claim, evidence, facts):
    """A conditional prohibition cannot support a different patient branch."""
    if name not in ('cpr', 'oral', 'oral_adjunct'):
        return True
    observations = {'consciousness': _consciousness, 'breathing': _breathing}
    if name in ('oral', 'oral_adjunct'):
        observations['swallowing'] = _swallowing
    for key, extract in observations.items():
        required = extract(evidence)
        stated = extract(claim)
        # Only unconditional advice can use the current patient's observations.
        if not _has(r'\b(?:if|when|se|quando|si|cuando)\b', claim):
            stated = stated or facts[key]
        if required and stated != required:
            return False
    if _has(r'\b(?:or|ou|o)\b', claim) and not _has(r'\b(?:or|ou|o)\b', evidence):
        return False
    return True


def _repeat_supported(claim, evidence):
    """Keep an explicit repeat's evidence interval and conditional restriction."""
    def repeats(text):
        return re.findall(r'\b(?:repeat|repita)\b(.*?)(?=\b(?:repeat|repita)\b|$)',
                          normalize(_CITE.sub('', text)))

    claimed, supported = repeats(claim), repeats(evidence)
    if len(claimed) > len(supported):
        return False
    for instruction, source in zip(claimed, supported):
        durations = {q for q in _quantities(source) if q[-1] in ('s', 'min')}
        if not durations.issubset(_quantities(instruction)):
            return False
        if durations and _has(r'\b(?:immediately|imediatamente|inmediatamente|now|agora|ahora)\b', instruction):
            return False
        condition = re.search(r'\b(?:if|unless|se|si)\b.*', source)
        if condition and condition[0] not in instruction:
            return False
    return True


def _evidence_units(text, name):
    """Keep device-specific timing clauses separate, with original offsets."""
    if name != 'injector_hold':
        return list(_units(text))
    result = []
    # These boundaries introduce a new timing instruction. Other rule families
    # retain sentence scopes, including the flood exception and repeat doses.
    boundary = re.compile(r';|(?:,?\s+(?:and|e|y)\s+|,\s*)(?=(?:for\s+)?'
                          r'(?:epipen|jext|auvi[ -]q|anapen|emerade)\b)', re.I)
    for unit, start, _ in _units(text):
        previous = 0
        for split in (*boundary.finditer(unit), None):
            end = split.start() if split else len(unit)
            result.append((unit[previous:end], start + previous, start + end))
            previous = split.end() if split else end
    return result


def _quantities(text):
    # Strip references before interpreting numbers; don't confuse [S20] with a dose.
    text = _CITE.sub('', text).casefold()
    for word, number in (('one','1'), ('two','2'), ('three','3'), ('five','5'), ('ten','10'), ('twenty','20')):
        text = re.sub(r'\b' + word + r'\b', number, text)
    units = {'seconds':'s', 'second':'s', 'segundo':'s', 'segundos':'s',
             'minutes':'min', 'minute':'min', 'minutos':'min', 'minuto':'min',
             'drops':'drop', 'drop':'drop', 'gotas':'drop', 'gota':'drop',
             'grams':'g', 'gram':'g', 'gramas':'g', 'grama':'g', 'gramos':'g', 'gramo':'g'}
    # Preserve quantities from every action, but distinguish subsequent actions
    # from the initial instruction. A wait duration cannot support cooling, and
    # a repeat dose cannot borrow the initial dose (or vice versa).
    actions = {
        'rest':'rest', 'descanse':'rest', 'wait':'wait', 'espere':'wait',
        'check':'check', 'recheck':'check', 'verifique':'check', 'compruebe':'check',
        'repeat':'repeat', 'repita':'repeat',
    }
    boundary = r'(?:\b(?:and|then|e|y|entao|luego)\s+|;\s*)(' + '|'.join(actions) + r')\b'
    segments = re.split(boundary, text)
    result = set()
    counts = {}
    for index in range(0, len(segments), 2):
        action = actions[segments[index - 1]] if index else 'initial'
        counts[action] = counts.get(action, 0) + 1
        for match in re.finditer(
                r'(?<![\w.])([0-9]+(?:[.,][0-9]+)?)\s*(seconds?|segundos?|minutes?|minutos?|ml|mg|mcg|g|grams?|gramas?|gramos?|drops?|gotas?|cm|mm|°c|°f)\b', segments[index]):
            result.add((action, counts[action], match[1].replace(',', '.'), units.get(match[2], match[2])))
    return result



def _scope_for_unit(units, index, name):
    raw = units[index][0]
    if name == 'cpr_continuation':
        if _has(r'\b(?:until|ate|hasta que)$', normalize(raw)):
            for following, _, _ in units[index + 1:]:
                if not re.match(r'\s*[*+-]\s+', following):
                    break
                raw += '\n' + following
        return raw
    if name in ('embedded_object', 'generator_shutdown', 'generator_reentry'):
        return raw
    # Only join the specific adjacent exception, never a random safety sentence.
    if raw.lstrip().startswith('#'):
        for following, _, _ in units[index + 1:]:
            if following.lstrip().startswith('#'):
                break
            raw += ' ' + following
    if index + 1 < len(units):
        following = units[index + 1][0]
        t = normalize(following)
        if (name == 'burn_clothing' and _has(_STUCK, t) and _has(_EXCEPT, t)) or (
                name == 'flood_wait' and _has(r'\b(?:rising|rises|subindo|subir|sube)\b', t) and _has(r'\b(?:roof|teto|techo)\b', t)):
            raw += ' ' + following
    return raw


def _matches(rule, text, evidence=False):
    if rule.name == 'generator_indoor' and not _has(r'\b(?:generator\w*|gerador\w*|generador\w*)\b', text):
        return []
    if rule.name == 'oral_adjunct' and not _has(r'\b(?:antihistamine\w*|antihistaminico\w*)\b', text):
        return []
    if evidence and rule.name == 'water_chemical' and not _has(r'\b(?:fuel|gasoline|petrol|toxic chemicals?|chemical contaminants?|combustivel|gasolina|quimic\w*|combustible)\b', text):
        return []
    return list(re.finditer(rule.pattern, text))


def check_claims(answer, sources, plan):
    """Return issue codes and per-claim source evidence for known action families."""
    issues, claims = [], []
    by_n = {str(s['n']): s for s in sources if not s.get('context_omitted')}
    question = normalize(' '.join((*plan.context_turns, plan.question)))
    facts = _facts(plan)
    units = list(_units(answer))
    topics = set(plan.topics)
    # The planner's topic IDs are retrieval hints; localized burn/fire mentions
    # in the question also establish applicability for these bounded guards.
    if _has(r'\b(?:burn\w*|scald\w*|queimadur\w*|quemadur\w*)\b', question):
        topics.add('burn')
    if _has(r'\b(?:fire|incendio|fogo|fuego)\b', question) and _has(r'\b(?:oil|grease|pan|oleo|gordura|aceite|sarten|frigideira)\b', question):
        topics.add('grease_fire')
    if _has(r'\b(?:wound\w*|bleed\w*|ferid\w*|herid\w*|sangr\w*)\b', question):
        topics.add('bleeding')
    for index, (raw, start, end) in enumerate(units):
        for rule in RULES:
            if rule.topics and not topics.intersection(rule.topics):
                continue
            if rule.name == 'oral' and not topics and not _consciousness(question) and not _has(
                    r'\b(?:glucose|glicose|glucosa|antihistamine\w*|antihistaminico\w*)\b', normalize(raw)):
                continue
            text = _claim_text(_CITE.sub('', raw), rule.name)
            for match in _matches(rule, text):
                positive = _polarity(rule, text, match)
                scope = _scope_for_unit(units, index, rule.name)
                scoped = _claim_text(_CITE.sub('', scope), rule.name)
                condition = _condition_issue(rule.name, scoped, question, positive)
                if condition:
                    issues.append(condition)
                cited = list(dict.fromkeys(_CITE.findall(scope)))
                supported, quantity_failure = [], False
                for n in cited:
                    source = by_n.get(n)
                    if not source:
                        continue
                    source_age = _age(normalize(source.get('text', '')))
                    if source_age and plan.scope.get('age_group') and source_age != plan.scope['age_group']:
                        continue
                    source_units = _evidence_units(source.get('text', ''), rule.name)
                    for si, (snippet, source_start, source_end) in enumerate(source_units):
                        candidate = _claim_text(snippet, rule.name)
                        matching = _matches(rule, candidate, evidence=True)
                        if not any(_polarity(rule, candidate, m) == positive for m in matching):
                            continue
                        if not positive and rule.name in ('embedded_object', 'generator_reentry') and _condition_issue(rule.name, candidate, question, False):
                            continue
                        if not positive and not _negative_scope_supported(rule.name, text, candidate, facts):
                            continue
                        if positive and rule.name in ('oral', 'oral_adjunct') and not _oral_objects(text).issubset(_oral_objects(candidate)):
                            continue
                        context = _claim_text(_scope_for_unit(source_units, si, rule.name), rule.name)
                        if positive and (not _source_conditions(rule.name, context) or
                                         _condition_issue(rule.name, context, question, True)):
                            continue
                        # Device and regional applicability must also be in the
                        # cited source, not invented by the generated answer.
                        if positive and rule.name == 'injector_hold':
                            devices = set(re.findall(_DEVICE, question))
                            claimed_devices = set(re.findall(_DEVICE, text))
                            if (not devices.intersection(re.findall(_DEVICE, candidate))
                                    or not claimed_devices.issubset(devices.intersection(re.findall(_DEVICE, candidate)))):
                                continue
                        if positive and rule.name == 'snake_compression':
                            if not _has(r'\baustrali\w*\b', context):
                                continue
                            # No species-identification/binding policy exists yet.
                            # Restricted passages cannot become universal advice.
                            if _has(r'\b(?:only for|only in|specific|certain|somente|apenas|solo|solamente)\b.{0,40}\b(?:species|especies)\b|\b(?:species|especies) specific\b', context):
                                continue
                        if not _quantities(raw).issubset(_quantities(snippet)):
                            quantity_failure = True
                            continue
                        if positive and rule.name in ('oral', 'oral_adjunct') and not _repeat_supported(raw, snippet):
                            continue
                        supported.append({'source_n':source['n'], 'span':[source_start, source_end],
                                          'text_sha256':hashlib.sha256(source['text'].encode()).hexdigest()})
                        break
                if not supported:
                    issues.append('claim_quantity_not_supported' if quantity_failure else 'claim_not_supported_by_cited_passage')
                claims.append({'rule':rule.name, 'answer_span':[start, end], 'positive':positive,
                               'cited_ids':cited, 'evidence':supported,
                               'status':'blocked' if condition or not supported else 'pattern_supported'})
    return list(dict.fromkeys(issues)), {'coverage':'known_patterns_only', 'claims':claims,
                                       'other_claims':'unverified'}
