"""Formatting must not lose evidence; related conditions must not supply claims."""
import unittest
from app.answer_validation import validate_answer
from app.engine import Engine

Q='An unidentified snake bit my leg.'
BAN='Do not use a tight arterial tourniquet.'
CARRY='Have helpers carry the person on a stretcher rather than making them walk.'


def source(text,n=1):
    return dict(n=n,id=f'source-{n}',kind='kit',text=text)


class GroundingRefinementTests(unittest.TestCase):
    def check(self,draft,evidence,allowed=True,issue=None):
        text,report=validate_answer(draft,evidence,Q)
        self.assertEqual(bool(text),allowed,report)
        if issue:self.assertIn(issue,report['issues'])
        return text,report

    def test_citations_after_closing_markdown_stay_attached(self):
        for draft in ('**Never use a tourniquet.** [S1], [S2]',
                      '*Never use a tourniquet.* [S1].',
                      '**Never use a tourniquet**. [S1].',
                      'Never use a tourniquet. [S1], [S2].'):
            with self.subTest(draft=draft):self.check(draft,[source(BAN),source(BAN,2)])

    def test_formatting_does_not_borrow_next_sentence_or_list_citation(self):
        for draft in ('**Never use a tourniquet.** Keep still [S1].',
                      '**Never use a tourniquet.**\n- Keep still [S1].',
                      '**Never use a tourniquet.**\n\n[S1]'):
            with self.subTest(draft=draft):self.check(draft,[source(BAN)],False)
        self.check('**Never use a tourniquet.** [S99]',[source(BAN)],False,'citation_not_supplied')

    def test_plain_carry_summary_links_to_equivalent_cited_repetition(self):
        draft='Have helpers carry you on a stretcher.\nHave helpers carry the person on a stretcher [S1].'
        text,report=self.check(draft,[source(CARRY)])
        self.assertIn('[1]',text.splitlines()[0])
        self.assertTrue(any(c.get('citation_binding') for c in report['claim_checks']['claims']))
        for intro in ('Have helpers carry you on a stretcher or chair.',
                      'Have helpers carry you because it stops venom.'):
            self.check(intro+'\nHave helpers carry the person on a stretcher [S1].',[source(CARRY)],False)

    def test_unconditional_passive_ban_can_supply_summary_citation(self):
        self.check('Do not use a tourniquet.\nA tight arterial tourniquet is contraindicated [S1].',[source(BAN)])
        self.check('Do not use a tourniquet.\nA tourniquet is contraindicated unless help is delayed [S1].',[source(BAN)],False)

    def test_causal_explanation_requires_its_own_matching_evidence(self):
        for draft in ('Tourniquets accelerate venom spread',
                      'A tourniquet can cause tissue damage',
                      'Tourniquets cut off blood flow',
                      'Walking accelerates venom effects'):
            with self.subTest(draft=draft):
                self.check(draft+' [S1].',[source(BAN)],False,'explanation_not_supported_by_cited_passage')
                self.check(draft+' [S1].',[source(draft)])
        self.check('Tourniquets accelerate venom spread [S1].',
                   [source('Walking accelerates venom effects.')],False,'explanation_not_supported_by_cited_passage')
        self.check('Tourniquets accelerate venom spread [S1].',
                   [source('Tourniquets do not accelerate venom spread.')],False,'explanation_not_supported_by_cited_passage')
        self.check('A tourniquet can cause tissue damage [S2].',
                   [source('A tourniquet can cause tissue damage.'),source(BAN,2)],False,'explanation_not_supported_by_cited_passage')

    def test_multilingual_venom_explanations_are_not_supported_by_a_ban(self):
        for draft in ('Torniquetes podem acelerar a disseminação do veneno',
                      'Los torniquetes pueden acelerar la propagación del veneno'):
            with self.subTest(draft=draft):
                self.check(draft+' [S1].',[source(BAN)],False,'explanation_not_supported_by_cited_passage')

    def test_tissue_damage_does_not_support_more_specific_injuries(self):
        self.check('A tourniquet can cause tissue damage, nerve injury and limb loss [S1].',
                   [source('A tourniquet can cause tissue damage.')],False,'explanation_not_supported_by_cited_passage')
        self.check('Aplicar un torniquete puede dañar tejidos [S1].',[source(BAN)],False,
                   'explanation_not_supported_by_cited_passage')

    def test_uncertain_cause_is_not_positive_evidence(self):
        self.check('Tourniquets accelerate venom spread [S1].',
                   [source('Tourniquets are not known to accelerate venom spread.')],False,
                   'explanation_not_supported_by_cited_passage')

    def test_pronoun_explanation_needs_support_and_cannot_borrow_a_walking_effect(self):
        self.check('Never use a tourniquet [S1]. It can cause tissue damage [S1].',
                   [source(BAN)],False,'explanation_not_supported_by_cited_passage')
        self.check('Never use a tourniquet [S1]. Isso pode acelerar a disseminação do veneno [S1].',
                   [source(BAN+' Walking accelerates venom effects.')],False,'explanation_not_supported_by_cited_passage')

    def test_scorpion_warning_cluster_cannot_support_snakebite_warning(self):
        warning='Repeated vomiting, heavy sweating and agitation are warning signs'
        self.check(warning+' [S1].',[source('Snakebite: keep still.\n\n**Scorpion:** '+warning+'.')],
                   False,'condition_detail_not_supported_by_cited_passage')
        self.check(warning+' [S1].',[source('Snakebite: '+warning+'.')])

    def test_direct_only_if_cpr_condition_is_not_overridden_by_earlier_or(self):
        good='Se houver dificuldade respiratória ou perda de consciência, inicie RCP (Reanimação Cardiopulmonar) apenas se a vítima não responder e não tiver respiração normal'
        self.check(good+' [S1].',[source(good)])
        bad=good.replace('não responder e não tiver','não responder ou não tiver')
        self.check(bad+' [S1].',[source(good)],False,'cpr_prerequisites_missing')
        self.check('If unconscious or not breathing, start CPR and keep still only if unresponsive and not breathing [S1].',
                   [source('Start CPR only if unresponsive and not breathing.')],False,'cpr_prerequisites_missing')

    def test_nominal_warning_is_not_an_instruction_but_still_needs_evidence(self):
        draft='O uso de torniquete ou garrote é perigoso e pode piorar o quadro ao cortar a circulação'
        _,report=self.check(draft+' [S1].',[source(BAN)],False,'explanation_not_supported_by_cited_passage')
        self.assertNotIn('snake_tourniquet_unsafe',report['issues'])

    def test_snakebite_retrieval_excludes_other_condition_blocks_without_editing_guides(self):
        engine=Engine({'kiwix_enabled':False})
        for lang in ('en','pt','es'):
            sources=engine.retrieve(Q,lang,use_kiwix=False)
            originals=[s for s in sources if '07-first-aid-medicine' in s['id']]
            self.assertTrue(originals)
            for s in originals:
                self.assertNotIn('Loxosceles',s['text'])
                self.assertNotIn('Scorpion',s['text'])
                self.assertNotIn('Escorpi',s['text'])
                self.assertTrue(s.get('parent_source_id'))
                self.assertTrue(s.get('retained_spans'))
        # Mixed requests retain the other condition, not silently truncate it.
        mixed=engine.retrieve('A snakebite and a scorpion sting. What should we do?', 'en',use_kiwix=False)
        self.assertTrue(any('**Scorpion:**' in s['text'] for s in mixed))
        negated=engine.retrieve('A snakebite, not a scorpion sting.', 'en',use_kiwix=False)
        self.assertFalse(any('**Scorpion:**' in s['text'] for s in negated))
