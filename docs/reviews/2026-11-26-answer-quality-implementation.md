# Answer-quality follow-up implementation

The approved design retains paraphrases and adds bounded checks and source-backed fallbacks. It does not certify medical accuracy or general semantic entailment. The standalone installation, original knowledge and archives are not modified by this implementation.

## Displayed behavior

Twelve versioned guidance units, with English/Portuguese/Spanish variants, enter evidence selection before conflict handling and context fitting. Source provenance is separate from local guides and Kiwix. Reviewed precedence still controls conflicts; catalog presence does not grant authority. A directly applicable local guide retains its place before supplemental guidance.

Rejected drafts remain buffered and undisplayed. Generation failure, unavailable models and validation failure can yield a deterministic composition of applicable complete guidance units. The composition is independently validated. Original failure reasons and generation metadata remain intact; fallback has separate metadata. Explicit search-only mode remains evidence browsing. When no eligible catalog guidance exists, the existing source-excerpt/limitation behavior remains; it is not labeled as validated advice.

Omitted model-context evidence can support fallback only when its original content and provenance match the canonical catalog. The evidence is marked separately and sent before citation tokens. Browser source cards update on each source event, with offline-readable evidence and publisher links. Fallback evidence cannot be forged merely by assigning a source kind or copied ID.

Known swallowing restrictions exclude oral guidance before composition. Nonoral hypoglycemia guidance retains explicit conditions for emergency escalation, recovery positioning and glucagon. Flood guidance preserves the rising-inside-vehicle branch, the closed-attic restriction and the building-roof necessity condition.

## Bounded checks

Recognized action families cover CPR, oral treatment/adjuncts, thermal-burn clothing/cooling, heat immersion, snake compression, injector use/timing, flood waiting, cooking-fire covering/extinguishers and chemical-water disinfection claims. Checks retain relevant patient conditions, regional/device scope, polarity, equipment and quantities. Known action families must be supported by their own cited source statements; a disease definition or unrelated topical passage cannot establish procedural support.

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
