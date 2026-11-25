# Source applicability and extraction

Implemented in the repository; the separate installation on port 8090 has not been updated or restarted.

## Changes

A shared passage-admission check now examines body text before local, HTML, or PDF evidence is ranked. It rejects observed clinician-only interventions, clinical resuscitation termination decisions, mixed adult/infant procedures for infant requests, and oral-treatment passages for an unresponsive patient. Candidate search metadata remains eligible for fetching. Checks do not delete or rewrite source documents or assign authority to Kiwix over local guides.

HTML extraction inherits explicit caution sentences instead of entire parent procedures containing the word “only.” Nested lists retain their indentation. Conditional warnings retain their enclosing condition where unambiguous; ambiguous conditional parent procedures are not inherited, including their nested warnings. Original parent sections remain available. This conservative choice may omit an inherited caution; it avoids presenting a conditional warning as an unconditional instruction in another procedure.

## Verification

- Frozen captured-source fixtures reproduce the CPR, IV diabetes treatment, mixed adult/infant, and anaphylaxis failures without requiring Kiwix or a model.
- Added boundary tests cover affirmative instructions after negation, passive CPR termination, conditional oral prohibitions, nested lists, localized scope warnings, and mixed procedural/caution paragraphs.
- The real captured WikiMed Choking article retains the unconscious-infant CPR section, mouth-and-nose wording, and abdominal-thrust caution without importing the parent's two-finger chest-thrust step.
- Full Python suite: 443 tests run, 16 skipped, no failures. Both JavaScript suites pass. Disabling the admission gate and restoring whole-parent caution inheritance each cause the new tests to fail; both mutations were restored.
- Fresh review found and resolved negation and conditional-inheritance bugs and approved the bounded change. All 46 original knowledge files match their recorded SHA-256 hashes.

## Retrieval tradeoff and remaining limits

The frozen 59-case retrieval replay loses matches to previously annotated clinical sections. The pre-change baseline matched 28/30 annotated sections; the final applicability replay matched 15/30. The thirteen lost matches concern CPR, anaphylaxis, and heatstroke sections that mix first aid with clinical procedures. Annotations have not been weakened or changed to disguise this loss. This is a real reduction in supplied evidence, even where excluding a particular section is intentional. Useful replacement evidence remains for CPR, anaphylaxis, heatstroke, and infant choking; diabetes coverage remains inadequate after excluding clinical algorithms and oral treatment for an unconscious patient: the final replay selects general disease and diagnostic-background passages, not an actionable first-aid procedure. This is a remaining relevance/evidence-gap issue, not a successful emergency answer.

Live inspection also exposed lower-ranked clinical passages replacing rejected ones. Added checks cover those observed thoracic procedures, injection and infusion dosing (including boluses/drips without an explicit IV label), ACLS drug instructions, and activated-charcoal instructions. The final replay summary and included section identities are saved in `2026-11-25-applicability-evidence.json`; full prompt/source output is `/tmp/emergency-applicability-final-eval.json`.

These are conservative checks for observed hazards, not a general clinical classifier. Other wording, unsupported languages, condition conflicts, and inappropriate source sections can escape them. Filtering changes evidence selection, not source correctness. This change does not validate generated claims or citations, repair the model's infant-breathing synthesis error, or guarantee abstention when evidence is inadequate. No generated-advice safety pass or release approval is claimed. The next evaluation must assess answer quality and remaining evidence gaps, rather than treating Kiwix presence or old section-match scores as safety measures.
