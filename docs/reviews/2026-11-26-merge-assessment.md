# Merge assessment against main

Decision: approve the branch as an incremental improvement over main `e44f0b0`. The acceptance criterion is net improvement with documented limitations, as requested by the user; a perfect answer-quality screen is not a prerequisite. The failed/incomplete quality evaluations remain unchanged.

The branch includes stronger multilingual action-condition checks, source-supported transport methods, prohibition handling, citation attachment, scoped local passages and a more useful fallback. Main lacks explicit stretcher transport and breathing monitoring in its snakebite fallback. Existing guides are preserved. Evaluation artifacts remain excluded from install archives.

[Exact comparison](../../tests/evals/emergency_advice/baselines/grounding-live-2026-11-26/main-comparison.json) replays the same twenty captured drafts and sources through both validators. Main releases 19; the candidate releases one. Counts alone are not a quality score. Inspection identifies substantive reasons for the stricter behavior: water without safe-swallowing prerequisites, tourniquet exceptions, compression without scope, unsupported transport methods and explanations. The candidate supplies the reviewed actionable fallback instead.

Tradeoffs accepted for this incremental merge: the Spanish coordinated prohibition false positive is a regression versus main, and Kiwix Spanish trial 2 withholding remains uncertain. These are outweighed by the known safety/grounding repairs and useful fallback, but remain follow-up tasks. The released unsupported elevation sentence passes both versions; this is an existing validation limitation, not a newly introduced capability regression. This comparison does not establish statistically better fresh generation from the same model, and no claim of general clinical certification is made.

Review covered correctness, tests, source/provenance preservation, module boundaries, dependency/security impact and bounded processing. No new dependency, network operation, production draft logging or installation change was added. The causal and section checks remain explicitly limited rather than presented as semantic verification.

Follow-up priorities: Spanish prohibition coordination; unsupported limb positioning and regional qualifications; source conclusion reversal; multilingual causal support; then broader multi-domain evaluation. Preserve the failing captures as regression evidence.

Pre-merge verification: 825 Python tests passed (20 skipped); all three JavaScript checks passed; diff whitespace checks passed. Inverting the new evidence-presence condition made regression tests fail; restoring the exact original bytes returned all thirteen grounding tests to passing.
