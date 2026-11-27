# Repeated citations and transport support

Implemented steps 3–4 in the snakebite validation worktree. The installed application is unchanged.

An uncited, plain tourniquet prohibition in the first three sentence/list units can use the citation on a later plain, unconditional prohibition. The original introductory claim is checked against that passage again. Successful links record both answer spans and source evidence, and add a visible citation beside the introduction. Conditional statements, extra explanations, explicit wrong citations, omitted sources and narrower prohibitions cannot supply this link. This is deliberately a limited rule, not general cross-sentence citation inference.

Snakebite carrying instructions now require cited carrying evidence. Recognized methods (stretcher, chair, arms and supporting weight) must be supported by the cited passage; a stretcher passage cannot justify an added chair or arms alternative. Explicitly negated methods cannot supply positive evidence. This checks source support, not whether a particular transport method is universally appropriate.

## Exact replay

`tests/evals/emergency_advice/baselines/snakebite-2026-11-26/citation-transport-replay.json` binds the ten original draft captures to current validator hashes and the preceding prohibition-parsing results. Original captures and their historical reviews are unchanged.

- English pressure trial 3 changes from blocked to passed; its introductory prohibition gains a visible citation from the later supported repetition.
- All three transport drafts change from passed to blocked. Trial 1 has both missing citation support and a cited unsupported arms alternative. Trials 2–3 have uncited introductory alternatives. Separate tests demonstrate that adding a citation does not make these unsupported methods pass.
- Portuguese pressure trial 1 remains passed.
- The remaining five pressure drafts stay blocked. English trial 1 has no matching plain unconditional donor and also lacks accepted support for its alcohol prohibition. The genuine tourniquet exception and scope/condition failures remain blocked.

Thus two of ten captured drafts pass this bounded gate. A higher blocking count alone is not an answer-quality improvement; new model-backed evaluation must check usefulness and unnecessary fallback as well as safety and citation errors.

## Verification and limits

Ten new regression tests cover English, Portuguese and Spanish, citation rendering, conditional and wrong-source controls, transport alternatives, negative evidence and the three original transport drafts. They initially failed before implementation. The complete Python suite contains 782 tests (20 skipped). Relevant UI and stream JavaScript tests and syntax checks pass.

Review covered source identity, rendering offsets, condition preservation, polarity, and scope outside snakebite. No new dependencies or production draft logging were introduced. Diagnostics continue to state known-pattern coverage and unverified general claim support. Novel paraphrases and unsupported causal explanations remain outside comprehensive semantic validation. A fresh model-backed multilingual run is the next step; this replay does not replace it.
