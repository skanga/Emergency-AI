# Action-condition references and bounded validation

These guards are integrated in main. This record retains primary sources, procedure boundaries and known limitations; current engineering and evaluation status is recorded separately. The three full generated answers and exact supplied source texts are preserved in `tests/fixtures/retrieval/final-action-failures.json`; duplicated retrieval metadata is omitted. Evaluation prompts and rubrics are unchanged.

| Guard family | Verified primary guidance | Boundary |
| --- | --- | --- |
| Embedded-object removal | [Red Cross life-threatening bleeding](https://www.redcross.org/take-a-class/resources/learn-first-aid/bleeding-life-threatening-external), embedded-object FAQ, checked 2026-11-26 UTC | Leave the object in place; apply pressure around it. Generated removal exceptions are not supported. |
| Generator shutdown and re-entry | [OSHA portable-generator CO alert](https://www.osha.gov/sites/default/files/publications/OSHA4105.pdf), checked 2026-11-26 UTC | Get to fresh air immediately; re-entry requires clearance by trained and properly equipped personnel. An evacuated group or closed garage door does not establish safe access. |

The implementation uses bounded EN/PT/ES action patterns and checks each recognized instruction against its own citation. Explicit prohibitions, including nested “do not return to turn off equipment,” remain valid. Professional-clearance clauses must attach directly to recognized re-entry wording; an unrelated action or later sentence cannot supply clearance. No new shutdown procedure or catalog guidance is introduced.

Limitations: generator checks use the existing `carbon_monoxide` planner topic. That topic can include general generator questions; affirmative shutdown advice may be withheld even in maintenance contexts. Remote shutdown is not independently established and is conservatively withheld. Professional-clearance paraphrases outside the listed patterns may also be withheld. Embedded-object patterns do not cover every synonym or pronoun reference. These are bounded regression guards, not general semantic verification or medical certification.

Spec-review corrections: wound/bleeding context now gates the embedded-object rule; clearly visible airway-object removal in an infant choking scenario remains outside this rule. Re-entry clearance rejects recognized alternative conditions (`or`, `ou`, `o si`, `o cuando`) in both generated instructions and cited evidence. Tests reproduced both review failures before the fixes; this remains bounded language matching.

A final observed Spanish CPR answer (`spanish-2.json`) is included in the fixture. [Red Cross adult cardiac arrest](https://www.redcross.org/take-a-class/resources/learn-first-aid/adult-cardiac-arrest), checked 2026-11-26 UTC, distinguishes takeover/beginning care from mere responder arrival and AED readiness from arrival. The additional `cpr_continuation` rule recognizes “continue until” and its localized forms under the existing CPR topic. An immediately following bullet list stays within that instruction; the next nonbullet ends it. Each bullet retains its own boundary, so normal breathing or takeover in one branch cannot justify arrival in another. The same check applies to cited evidence. Valid takeover, normal breathing, exhaustion, unsafe-scene and AED-directed-pause counterparts pass. The actual captured answer and EN/PT/ES arrival variants failed before implementation.

This does not fix the captured answer's separate blanket movement restriction or certify every CPR instruction. Other stopping paraphrases and numbered continuation lists remain outside this bounded guard. The guard does not create a new CPR procedure or change the catalog.

Quality-review correction: every arrival mention in a continuation branch is checked independently. An earlier responder takeover cannot authorize a later bare AED arrival within the same sentence. EN/PT/ES claim and cited-source regressions failed before this change and pass afterward; valid takeover counterparts remain accepted.

## Burn follow-up after routing captures

Two full Spanish answers from the frozen routing candidate are preserved in `tests/fixtures/retrieval/burn-action-failures.json`, with exact supplied source text. One allowed separating clothing unless it was firmly stuck; the other instructed leaving jewelry until swelling. Both contradicted the supplied burn passage's stuck-item exception and early jewelry removal. The existing [NHS burns guidance](https://www.nhs.uk/conditions/burns-and-scalds/) and [St John Ambulance burn guidance](https://shop.sja.org.uk/blogs/workplace-first-aid/how-to-treat-burns-and-scalds) remain the reference basis; no clinical text or catalog unit changed.

The clothing guard now recognizes bounded separation/removal verb forms in EN/PT/ES. An adjacent degree qualifier before or after “stuck” cannot narrow the protection to firmly stuck material. The existing source-condition path applies the same check to evidence. Spanish negative attempt inflections preserve explicit prohibitions such as “Nunca intentes quitar.” A small burn-only jewelry pattern rejects affirmative keep/leave instructions linked to waiting for swelling; normal removal, leaving stuck jewelry alone, and explicit prohibitions remain accepted in the focused tests.

## Current follow-up

The completed repeated runs are recorded in [answer-quality results](../../tests/evals/emergency_advice/RESULTS.md). Current source mappings are in [guidance sources](guidance-sources.md). Keep the references, fixture links and limitations here even after implementation plans are removed. Do not infer complete semantic validation from these bounded guards.


## Original release-check references

The first release checks used [Red Cross unresponsive/breathing guidance](https://www.redcross.org/take-a-class/resources/learn-first-aid/unresponsive-and-breathing-person), [NHS hypoglycaemia guidance](https://www.nhs.uk/conditions/low-blood-sugar-hypoglycaemia/) for oral-intake restrictions, and [NHS child resuscitation guidance](https://www.nhs.uk/baby/first-aid-and-safety/first-aid/how-to-resuscitate-a-child/) for the captured infant-technique regression. Those checks were recorded on 2026-11-25; this cleanup does not renew them. Current infant catalog source differences are explained in [guidance sources](guidance-sources.md). Frozen release failures remain in `tests/fixtures/answer_release.json`.

## November 27 condition refinements

Tourniquet instructions retain life-threatening limb applicability and restrictions in their cited source; equipment inventory is not procedure evidence. Lone-snakebite movement retains necessity plus a known safe route, including negation and alternative-condition checks. CPR recognizes bounded gasping/abnormal-breathing paraphrases while retaining the unresponsive AND abnormal-breathing requirement. Portuguese `de` is not an oral-action verb; explicit `dê` remains subject to intake checks. See `tests/test_actionable_fallbacks.py` for supported and rejected counterparts. These patterns do not establish general entailment or complete coverage of arbitrary wording.

## Working-tree repairs after the full-main evaluation

Heat shutoff now requires its own safe-approach qualification. Staying in a flooded vehicle requires trapped/fast-moving-water scope and the rising-inside roof exception. Recognized repeat-injector instructions cannot use initial-dose evidence, substitute a different interval, or borrow a matching interval from an unrelated retrieved source. Explicit six-minute/persistent-symptom user context can support an immediate second injector; a one-minute history cannot.

Bounded same-line citation linking, plain CPR-prohibition linking, explicit AND-list prerequisites, stuck-clothing exceptions and condition-qualified food-menu evidence reduce false positives. Linking adds visible citations and checks the original instruction; it does not borrow another sentence's safety prerequisites. This is known-pattern validation, not general entailment. Negative controls retain OR, unsafe swallowing, wrong quantities and regional snake-cleaning restrictions. [Replay, live results and unresolved examples](../../tests/evals/emergency_advice/baselines/condition-fixes-2026-11-27/README.md).
