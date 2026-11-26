# Answer-quality follow-up implementation

The approved design retains paraphrases and adds bounded checks and source-backed fallbacks. It does not certify medical accuracy or general semantic entailment. The standalone installation, original knowledge and archives are not modified by this implementation.

## Displayed behavior

Twenty-two versioned guidance units, with English/Portuguese/Spanish variants, enter evidence selection before conflict handling and context fitting. Source provenance is separate from local guides and Kiwix. Reviewed precedence still controls conflicts; catalog presence does not grant authority. A directly applicable local guide retains its place before supplemental guidance.

Rejected drafts remain buffered and undisplayed. Generation failure, unavailable models and validation failure can yield a deterministic composition of applicable complete guidance units. The composition is independently validated. Original failure reasons and generation metadata remain intact; fallback has separate metadata. Explicit search-only mode remains evidence browsing. When no eligible catalog guidance exists, the existing source-excerpt/limitation behavior remains; it is not labeled as validated advice.

Omitted model-context evidence can support fallback only when its original content and provenance match the canonical catalog. The evidence is marked separately and sent before citation tokens. Browser source cards update on each source event, with offline-readable evidence and publisher links. Fallback evidence cannot be forged merely by assigning a source kind or copied ID.

Known swallowing restrictions exclude oral guidance before composition. Nonoral hypoglycemia guidance retains explicit conditions for emergency escalation, recovery positioning and glucagon. Flood guidance preserves the rising-inside-vehicle branch, the closed-attic restriction and the building-roof necessity condition.

## Bounded checks

Recognized action families cover CPR, oral treatment/adjuncts, thermal-burn clothing/cooling, heat immersion, snake compression, injector use/timing, flood waiting, cooking-fire covering/extinguishers chemical-water disinfection claims, indoor-generator use and sensory judgments of food safety. Checks retain relevant patient conditions, regional/device scope, polarity, equipment and quantities. Known action families must be supported by their own cited source statements; a disease definition or unrelated topical passage cannot establish procedural support.

Source checks retain decimal values, distinguish initial/repeated doses and repeat restrictions, and keep device-specific timing clauses separate. Source conditions are checked as well as generated conditions. Diagnostics identify rule, offsets and source hashes without storing rejected drafts. Overall `claim_support` remains `not_verified`; `pattern_supported` applies only to a bounded recognized claim, not the whole answer.

Unrecognized wording, complex condition relationships and nonprocedural explanations remain outside deterministic coverage. An ambiguous or species-restricted procedure may be withheld even when a qualified human could establish support. No automatic online verifier or second-model judge is added.

## Verification

- Failing-first tests cover each new policy and every concrete review finding, including decimal-dose bypasses, reversed conditions, unrelated negations, different medication/device support and unsafe scope borrowing.
- The seven targeted failures in the prior versioned eval are replayed with migrated valid citation IDs. They reject for condition/support defects rather than unknown citation IDs.
- Every catalog unit/language is checked with its own source citation; known-unsafe patient branches and conflict paths have integration tests.
- Disabling the claim checker causes three selected regressions to fail. Bypassing conflict filtering causes the policy-error regression to fail. Both mutations were process-local and restored.
- UI tests exercise source-before-citation ordering, offline readable evidence and unsafe URL rejection.
- Archive tests verify production guidance is included while `tests/` remains excluded in ZIP and tar exports.
- Final pre-evaluation Python suite: 700 tests run, 20 skipped, no failures. Both JavaScript test scripts and JavaScript syntax checks pass. A scheduler-sensitive existing retrieval test was corrected to assert started/unstarted candidate accounting rather than assuming four threads start within 30 ms under model load; production retrieval code was unchanged.
- Live-evaluation results are recorded in the final eval report rather than inferred from these checks.

Two-stage reviews covered specification compliance and code quality. Findings were fixed and rechecked; final reviewers approved the bounded catalog/engine/UI and claim-check scope. This is agent engineering review, not independent clinical or native-language adjudication.

## Live comparison

The baseline uses isolated code at `aff2ec4` on port 8190. The candidate is launched separately after its code is frozen. Both reuse the existing local model/Kiwix services with the same settings and knowledge. Baseline generation runs first, then candidate generation, avoiding concurrent inference; execution-order and sampling limitations remain. Existing 32-case rubrics are unchanged. Twelve additional development boundaries are stored separately and are not represented as a holdout.

## Refinement driven by the first frozen candidate

Candidate `0d2e1fa` remained frozen while the second worktree addressed its observed omissions. The catalog adds practical adult CPR, age-specific infant choking/CPR, trained tourniquet use, stroke, swallowed poison, carbon monoxide, prescribed allergy plans and outage food safety. All procedural conditions remain in displayed text. The infant 30:2 instructions explicitly identify a single rescuer; the AHA 2025 primary reference supports the selected technique. Reference differences and remaining translation/clinical review limits are recorded in the guidance-source review.

Two generated trial-two failures became permanent replay fixtures: a ventilation exception to the indoor-generator prohibition and sensory judgments of food safety after an outage. Bounded guards reject these patterns, including translated variants, while allowing unconditional prohibitions. The references were checked against CDC generator safety and CDC/FDA emergency food safety; they do not establish complete semantic coverage of either domain.

The command line now displays publisher URLs for guidance sources and labels fallback mode without requiring local-guide path fields. CPR search aliases recognize chest compressions in all three languages. Explicit under-one-year boundaries retain infant scope without overriding an earlier numeric patient age. All fixes have failing-first regression tests.

The first candidate's failed captures remain part of the evaluation record. The refinement is prepared for a separate freeze and run against the same 32 cases for three trials, followed by the twelve distinct development boundaries. No historical rubric is rewritten to improve the score.

Refinement verification: full Python suite ran 717 tests with 20 skips and no failures. After the final generator exception adjustment, 61 claim/catalog tests passed. Both JavaScript tests and syntax checking passed. Independent specification and code-quality reviews approved the bounded changes. The quality reviewer independently reran 80 focused tests and verified all 22 catalog hashes/66 translations. A process-local mutation removing the new hazard conditions caused regression failures and was restored.

Before the refined live run began, the independent rating audit found that the burn fallback omitted loose covering, body warmth and a direct ice prohibition. The unused server was stopped, the source-backed unit was corrected in all three languages, and specification/quality review approved the correction. The final full suite ran **718 tests, 20 skipped, no failures**. This was a prelaunch correction: no refined model captures were discarded or overwritten. The initial candidate's 96 captures and calibrated reviews are preserved under `tests/evals/emergency_advice/baselines/repeated-2026-11-26/`.

The full `ecf0d23` run exposed additional generated exceptions involving embedded objects, CO shutdown/re-entry and CPR stopping at mere arrival of help. Those captures remain intact. A separate worktree adds bounded guards and affected-case selection for the follow-up evaluation; see `2026-11-26-final-action-guards.md`. Final integration tests: **732 run, 20 skipped, no failures**, plus passing JavaScript checks. Passing these engineering checks does not replace the recorded answer-quality outcomes or the declared coverage limits.

The separate development run exposed three natural-language routing misses. The bounded vocabulary correction and its validation are recorded in `2026-11-26-routing-followup.md`. The final full engineering suite for that correction ran **737 tests, 20 skipped, no failures**. It changes topic selection rather than adding clinical instructions or declaring unrecognized claims verified.

Correct source retrieval did not itself prevent two subsequent Spanish burn instruction reversals. The final burn-condition correction and exact captured regressions are recorded in `2026-11-26-final-action-guards.md`. Latest complete engineering verification: **740 tests run, 20 skipped, no failures**, with independent specification/quality approval. Unrecognized wording remains outside verified coverage.
