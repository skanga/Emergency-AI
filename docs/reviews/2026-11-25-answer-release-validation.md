# Action conditions and citation validity

Implemented locally. Paraphrased answers remain enabled, as requested. The installed app on port 8090, original knowledge, model, and Kiwix archives were not changed. Changes are not committed or deployed.

## Release behavior

Generated prose is buffered until completion and validation. A rejected draft never appears in token events. The response buffer is capped at 128 KiB; incomplete or failed generation does not release partial instructions. Existing source/retrieval events remain available while generation runs. Waiting for the full answer increases the delay before substantive answer text appears.

Application references use `[S1]` in model input/output and are rendered as the existing `[1]` display references only after validation. Original source footnotes and citation-like markers are distinguished in prompt and extractive display; original source objects remain intact. The validator checks against the evidence actually retained after token fitting, rejects unknown/omitted IDs, malformed references, numeric source-footnote citations, and attached replacement links. Very long IDs are checked as strings rather than converted to integers. Ordinary code examples retain their array/index syntax.

The action guard checks recognized CPR prerequisites, oral-intake prerequisites, infant technique mismatches, and regenerated clinical procedures already excluded by the applicability boundary. It retains compatible prior user turns with their sentence boundaries, applies updates chronologically, and does not use assistant assertions as patient facts. Conditional statements cannot substitute an OR for required combined conditions or contradict a stated unsafe swallowing condition. Recognized procedural instructions need citations; headings may use citations in their own section.

A validation rejection produces a localized withholding notice and retains the references for inspection. It does not automatically rewrite the failed instruction or display the rejected draft. `generation.validation` records status, reason codes, cited IDs, and the limited checks performed. It always reports `claim_support: not_verified`; `passed` is not a clinical approval. Search-only passages remain evidence excerpts rather than validated generated instructions.

## Evidence and tests

- 33 release tests cover captured failures, positive counterparts, split chunks, incomplete/error streams, buffer limits, omitted references, namespace collisions, malformed/oversized IDs, link overrides, multilingual conditions, updated patient facts, recipes, and code examples.
- All six captured failing answers are rejected for their expected defect after valid historical citations are migrated to the new namespace. This separates action-condition checks from rejection merely because the citation protocol changed.
- Six new live drafts were generated using the existing local model and current retrieval. The final engine then replayed those drafts in 17-character chunks with their recorded fitted evidence. Four passed these limited checks; Portuguese CO and unconscious-diabetes drafts were withheld. The former repeated the disjunctive CPR condition; the latter added clinical-treatment discussion and unsupported instructions. These are six samples, not a statistical quality or clinical safety evaluation.
- Initial overblocking of a cited procedure heading and negative food/drink warnings was reproduced and corrected with tests.
- Full Python suite: 476 tests run, 16 skipped, no failures. Fresh code review approved this bounded change. Both JavaScript suites pass. Removing citation membership enforcement causes the release regression tests to fail; the mutation was restored.
- All 46 original knowledge files still match the recorded hashes.

Compact replay evidence: [answer-release evidence](2026-11-25-answer-release-evidence.json). Frozen captured-answer regressions: [test fixtures](../../tests/fixtures/answer_release.json). Full local live drafts and outputs: `/tmp/answer-release-smoke.json`; these diagnostic drafts are not included in application validation metadata.

## Policy basis and limits

The CPR condition is grounded in [American Red Cross guidance](https://www.redcross.org/take-a-class/resources/learn-first-aid/unresponsive-and-breathing-person). Oral-intake restrictions for an unconscious patient are supported by [NHS hypoglycaemia guidance](https://www.nhs.uk/conditions/low-blood-sugar-hypoglycaemia/). The infant technique regression was checked against [NHS child resuscitation guidance](https://www.nhs.uk/baby/first-aid-and-safety/first-aid/how-to-resuscitate-a-child/). Sources checked 2026-11-25. These references support the selected constraints, not certification of the implementation or generated answers.

The guard recognizes a bounded set of patterns. It can miss unfamiliar wording, complex clause relationships, unsupported languages, or other actions; conservative handling can withhold valid prose. Citation membership does not prove that the cited source supports the associated claim. Incorrect explanations and unsupported claims outside recognized action patterns can still pass. Source accuracy, broader relevance, adequate first-aid coverage, and full semantic or clinical validation remain separate evaluation needs.
