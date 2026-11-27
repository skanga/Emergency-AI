# Snakebite prohibition regression plan

Goal: reject the captured invented tourniquet exception while preserving supported paraphrases and useful fallback guidance.

Design: extend the existing bounded claim validator with a snakebite-specific tourniquet rule. Recognize both direct instructions and prohibitions expressed as recommendations. Keep arterial tourniquets separate from pressure immobilization, and check every matching clause against its own cited evidence. Do not apply the snakebite prohibition to unrelated severe-bleeding questions. Preserve existing pressure-bandage applicability checks and diagnostic limits; this is not general semantic verification.

Alternatives considered: prompt-only changes cannot enforce the release gate; source-exact answers conflict with the agreed paraphrase policy. A bounded validator extension fits the current architecture and the captured failure.

- [x] Reproduce the captured snake_pressure trial 2 failure from the committed authority run. Add EN/PT/ES prohibition, exception, polarity, citation, and unrelated-action controls in tests/test_snakebite_validation.py.
- [x] Run the new tests and record genuine behavior failures before editing app/claim_validation.py.
- [x] Add the smallest rule and scoped condition/polarity checks needed. Keep source support checks and rejected-draft privacy intact.
- [x] Verify rejected model output uses the existing useful snakebite fallback through Engine, and supported prohibitions still release.
- [x] Replay all 16 captured authority answers through old/new validation; inspect newly blocked answers for false positives. Run repeated isolated model checks if the service is available.
- [x] Run the full Python suite and relevant JavaScript checks; review the diff; record results and remaining limits in docs/reviews. Do not change the installed application or commit/push without a new request.

Baseline: 55 claim validation tests pass on e44f0b0. WHO Box 1 was checked on 2026-11-26: its arterial-tourniquet prohibition has no exception; pressure immobilization has separate applicability conditions.

Execution evidence: docs/reviews/2026-11-26-snakebite-prohibitions.md. Initial final-code model-backed attempts were blocked by unavailable services and a CUDA startup failure; the restored-model repeat is now complete, with ten reviewed captures and an incomplete quality screen. Offline fallback captures and interim live captures are retained separately.

- [x] After restoring a working model service, repeat the final-code English/PT/ES generated-answer evaluations and review usefulness, safety, citations and withholding.

- [x] Inspect a new ten-request repeat with evaluation-only draft capture. Original eight hidden drafts cannot be reconstructed. Findings: docs/reviews/2026-11-26-snakebite-draft-inspection.md.
- [x] Steps 1–2: repair demonstrated negative grammar/source-list parsing and distinguish warnings from instructions; replay all ten captured drafts and run the full suite.
- [x] Steps 3–4: resolve repeated-citation policy and unsupported transport paraphrases. Exact replay and regression evidence: docs/reviews/2026-11-26-citation-transport.md.
- [x] Step 5: repeat model-backed multilingual evaluation. All ten generations completed; all used fallback. Findings and remaining defects: docs/reviews/2026-11-26-snakebite-steps34-live.md. Completion is not a quality pass.
- [x] Repair the captured condition-detection gaps and demonstrated parsing/citation forms; improve transport fallback. Regression evidence: docs/reviews/2026-11-26-snakebite-gap-fixes.md.
- [x] Inspect the final-code repeat and record remaining language/source-support limitations separately from repaired fixtures: ten complete generations, two generated answers, eight improved fallbacks; not a broad quality pass.
- [x] Address the recorded compound/adjective prohibitions, swallowing/offer verb variants and unspecified transport alternatives. Follow-up audit and remaining general quality limits: docs/reviews/2026-11-26-safety-detection-audit.md.
- [ ] Broader Kiwix-enabled answer-quality screening.
