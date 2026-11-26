"""Repeated warnings need equivalent evidence; transport methods cannot drift."""
import json
from pathlib import Path
import unittest

from app.answer_validation import validate_answer

ROOT = Path(__file__).resolve().parents[1]
Q = 'A snake bit my leg. Should people carry me to transport?'
BAN = 'Do not use a tight arterial tourniquet.'
CARRY = 'Have helpers carry the person on a stretcher to transport rather than making the person walk.'


def source(text, n=1, **extra):
    return dict(n=n,id=f'source-{n}',kind='kit',text=text,**extra)


class ClaimLinksTransportTests(unittest.TestCase):
    def check(self, answer, passages, allowed=True, issue=None, lang='en'):
        rendered, report = validate_answer(answer,passages,Q,lang)
        self.assertEqual(bool(rendered),allowed,report)
        if issue:self.assertIn(issue,report['issues'])
        return rendered, report

    def test_plain_intro_links_to_same_later_prohibition_and_displays_citation(self):
        for intro, later in (
            ('Do not tie a tight band or tourniquet.', 'Never apply a tourniquet'),
            ('**NO. Do not tie a tight band or tourniquet.**', '* Do not apply a tight tourniquet or tight bandage'),
            ('Não aplique torniquete nem garrote.', 'Não use torniquete nem garrote'),
            ('No apliques un torniquete.', 'No debe aplicar un torniquete'),
        ):
            with self.subTest(intro=intro):
                rendered,report=self.check(intro+'\n\n'+later+' [S1].',[source(BAN)])
                self.assertIn('[1]',rendered.split('\n\n')[0])
                linked=[c for c in report['claim_checks']['claims'] if c.get('citation_binding')=='repeated_prohibition']
                self.assertTrue(linked)
                self.assertTrue(all(c['evidence'] and c['citation_answer_span'] for c in linked))

    def test_no_link_from_different_action_or_conditional_or_unsupported_warning(self):
        cases=[
            ('Never use a tourniquet.\nKeep still [S1].',BAN),
            ('Never use a tourniquet.\nDo not use a tourniquet unless help is delayed [S1].',BAN),
            ('Do not use a tourniquet if the snake is unknown.\nNever use a tourniquet [S1].',BAN),
            ('Never use a tourniquet.\nNever use a tourniquet [S1].','Keep still.'),
            ('Never use a tourniquet.\nTourniquets can cause damage [S1].',BAN),
            ('Never use a tourniquet.\nNever use a narrow tourniquet [S1].','Never use a narrow tourniquet.'),
            ('Never use a tourniquet.\nNever use a tourniquet [S99].',BAN),
        ]
        for answer,evidence in cases:
            with self.subTest(answer=answer):self.check(answer,[source(evidence)],False)
        self.check('Never use a tourniquet.\nNever use a tourniquet [S1].',
                   [source(BAN,context_omitted=True)],False)

    def test_extra_intro_claim_does_not_inherit_ban_citation(self):
        answer='Never use a tourniquet because it stops venom.\nNever use a tourniquet [S1].'
        self.check(answer,[source(BAN)],False,'claim_not_supported_by_cited_passage')

    def test_explicit_wrong_citation_is_not_repaired(self):
        self.check('Never use a tourniquet [S2].\nNever use a tourniquet [S1].',
                   [source(BAN),source('Keep still.',2)],False,'claim_not_supported_by_cited_passage')

    def test_stretcher_and_generic_carrying_have_supported_paraphrases(self):
        for answer in ('Have helpers carry you on a stretcher', 'Have people carry you',
                       'Use a stretcher to carry the person', 'Have the person carried on a stretcher'):
            with self.subTest(answer=answer):
                _,report=self.check(answer+' [S1].',[source(CARRY)])
                self.assertTrue(any(c['rule']=='snake_transport' and c['evidence'] for c in report['claim_checks']['claims']))

    def test_stretcher_source_cannot_support_added_transport_alternatives(self):
        for answer in ('Have helpers carry you on a stretcher or chair',
                       'Have helpers carry you on a stretcher or in arms',
                       'Have helpers carry you in their arms',
                       'Have helpers carry you on a stretcher or support your weight while they move you quickly',
                       'Have people carry you on a stretcher or in your arms immediately'):
            with self.subTest(answer=answer):
                self.check(answer+' [S1].',[source(CARRY)],False,'transport_method_not_supported')

    def test_transport_citation_must_support_positive_action_and_method(self):
        for evidence in ('Do not carry the person on a stretcher.', 'Keep still and arrange urgent transport.'):
            self.check('Have helpers carry you on a stretcher [S1].',[source(evidence)],False,
                       'claim_not_supported_by_cited_passage')
        self.check('Have helpers carry you in a chair [S1].',[source(CARRY),source('Have helpers carry the person in a chair.',2)],
                   False,'transport_method_not_supported')
        self.check('Have helpers carry you in a chair [S2].',[source(CARRY),source('Have helpers carry the person in a chair.',2)])

    def test_negated_or_alternative_methods_do_not_count_as_positive_evidence(self):
        self.check('Have helpers carry you in a chair [S1].',
                   [source('Have helpers carry the person on a stretcher, not in a chair.')],False)
        self.check('Have helpers carry you on a stretcher, not in a chair [S1].',[source(CARRY)])

    def test_multilingual_transport_boundaries(self):
        for lang,good,bad,evidence in (
            ('pt','Peça que carreguem a pessoa em uma maca','Peça que carreguem a pessoa em uma maca ou cadeira','Carreguem a pessoa em uma maca.'),
            ('es','Que lleven a la persona en una camilla','Que lleven a la persona en una camilla o silla','Lleven a la persona en una camilla.'),
        ):
            with self.subTest(lang=lang):
                self.check(good+' [S1].',[source(evidence)],lang=lang)
                self.check(bad+' [S1].',[source(evidence)],False,'transport_method_not_supported',lang)

    def test_original_transport_additions_are_blocked(self):
        p=ROOT/'tests/evals/emergency_advice/baselines/snakebite-2026-11-26/draft-inspection.json'
        for row in json.loads(p.read_text(encoding='utf-8'))['results']:
            if row['id']!='snake_transport':continue
            c=row['validation_inputs'][0]
            with self.subTest(trial=row['trial']):
                self.check(c['draft'],c['sources'],False)
