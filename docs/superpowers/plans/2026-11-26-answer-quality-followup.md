# Answer-quality follow-up implementation plan

> Execute using subagent-driven-development with spec and code-quality review. Keep tests and run evidence in Git, excluded from installation archives. The approved design is `../specs/2026-11-26-answer-quality-followup-design.md`.

**Goal:** Deliver useful source-backed fallbacks, bounded action and citation-support checks, and a reproducible three-trial comparison.

**Architecture:** A small guidance catalog supplies explicitly scoped evidence. A separate claim-check module validates recognized actions against their own citations. Engine orchestration preserves rejection and conflict states and emits catalog fallbacks independently from rejected drafts.

**Tech stack:** Python standard library, unittest, existing local llama.cpp/Kiwix, existing eval runner.

## 1. Baseline and regression evidence

- [x] Run `python3 -m unittest discover -s tests` in the clean worktree; retain count and failures.
- [x] Launch baseline `aff2ec4` on an isolated loopback port against the existing model and Kiwix services, recording paths, settings hashes and source identities. Do not restart the installed application.
- [x] Run `python3 tests/evals/emergency_advice/runner.py run --url http://127.0.0.1:8190 --output /tmp/advice-quality-baseline --trials 3`; retain all 96 outcomes without retries or overwrites.
- [x] Review each answer and cited passage using the existing rubric and exact review bindings. Preserve compact evidence under `tests/evals/emergency_advice/`.

## 2. Guidance catalog (`app/guidance.py`, `app/data/guidance.json`, `tests/test_guidance.py`)

- [x] Verify primary references, save claim/source mapping and limits in a review document, author short en/pt/es guidance units with stable IDs and hashes.
- [x] Test `guidance_sources(plan, lang)` returns eligible, complete source objects; facts come only from compatible user turns; unknown scope stays conditional; search words in unrelated contexts do not select hazardous actions.
- [x] Test `fallback_answer(sources, lang, conflicts)` returns text and selected IDs without using generated prose; missing/policy-error/contested evidence fails closed.
- [x] Implement catalog loading/hash validation, bounded selection and rendering; preserve source IDs and original evidence. Test changed hashes and omitted sources explicitly.
- [x] Run `python3 -m unittest tests.test_guidance`; perform spec and quality review.

## 3. Known action and source-support checks (`app/claim_validation.py`, `tests/test_claim_validation.py`)

- [x] Reproduce missing burn, airway, swallowing, regional snake, injector, flood and cooking-fire conditions with valid counterparts.
- [x] Reproduce citation-to-definition, unrelated water evidence, wrong numerical timing and condition/polarity mismatch with valid supported paraphrases.
- [x] Implement `check_claims(answer, sources, plan)` returning issue codes and bounded claim diagnostics. Validate only cited passages, never the whole retrieval set. Record source spans/hashes but no rejected draft in diagnostics.
- [x] Require exact values/units for recognized quantitative claims and their own action evidence. Do not claim universal entailment; expose unverified coverage.
- [x] Run `python3 -m unittest tests.test_claim_validation`; mutate critical guards and confirm tests fail, then restore. Perform spec and quality review.

## 4. Engine integration (`app/engine.py`, `app/answer_validation.py`, `app/i18n.py`, `tests/test_answer_release.py`, web source labels if needed)

- [x] Write failing integration tests for useful fallback on invalid/incomplete/unavailable generation, search-only preservation, source event order, context omission, unresolved conflicts and policy-load errors.
- [x] Admit guidance before conflict evaluation and prompt fitting without hiding local guides or assigning automatic precedence. Label its provenance separately from Kiwix.
- [x] Apply bounded claim checks in `validate_answer`; keep rejected drafts buffered and absent from ordinary metadata.
- [x] Use deterministic eligible fallback after failure, with independent fallback metadata and original failure reason. Restore omitted catalog evidence only as explicitly marked fallback evidence before citations.
- [x] Run focused release/guidance/claim tests and full Python suite plus existing JavaScript tests. Verify installation archives include production catalog and exclude evals.
- [x] Obtain spec review then quality review; fix findings before live candidate evaluation.

## 5. Repeated candidate evaluation and report

- [ ] Launch candidate on isolated loopback with baseline-identical model/data configuration and record exact candidate file hashes.
- [ ] Run all 32 cases for three trials into `/tmp/advice-quality-candidate`; retain failed runs and any subsequent affected-group reruns separately.
- [ ] Review every displayed answer and source against unchanged rubrics; report four dimensions separately, including fallback usefulness and unknown drafts.
- [x] Add distinct development boundary variants for new conditions; do not relabel them as holdouts or rewrite historical rubrics.
- [ ] Save compact evidence, bound reviews, reproducible comparisons and provenance in Git. Record full-suite results, mutation results and platform limits.
- [ ] Update remaining-work status accurately. A completed implementation/evaluation can still fail the quality screen; independent clinical adjudication remains external.
