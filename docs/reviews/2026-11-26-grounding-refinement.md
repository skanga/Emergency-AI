# Withholding and grounding refinements

Scope: implement the requested next steps 1–2 after the safety-detection audit. Preserve paraphrases, known action conditions and explicit validation limits. Fresh model-backed multilingual and Kiwix evaluation remains the next step.

## Changes

- Keep citations immediately after closing Markdown and sentence punctuation attached to the preceding claim. Never borrow citations across paragraphs or from the next instruction.
- Link a plain repeated carry instruction or unconditional tourniquet prohibition to an equivalent cited repetition, rechecking its evidence and transport method. Insert the verified citation into the displayed summary. Exceptions, added methods and causal explanations cannot inherit this link.
- Recognize the captured Portuguese nominal warning as a warning rather than a positive instruction. Separately require evidence for recognized causal explanations.
- Treat directly attached CPR “only if” prerequisites as mandatory even after an earlier broad warning with “or”. Preserve rejection of OR inside prerequisites and prevent another action from lending its conditions.
- For snakebite-only local retrieval, exclude complete labelled scorpion/spider paragraphs. Keep original guide files intact, retain source attribution and record parent identity, hashes and retained spans. Mixed requests retain the other condition; an explicit negated mention does not request it.
- Check bounded causal subject/effect/polarity relationships against the cited passage. A prohibition does not substantiate a harm explanation; movement effects cannot substantiate tourniquet effects; generic tissue damage does not substantiate nerve injury or limb loss. Recognize adjacent unambiguous pronouns and uncertain evidence conservatively.
- Check the recurring vomiting/sweating/agitation warning cluster against same-condition evidence. This does not claim these symptoms never occur in snakebite.
- Prompt the model to cite summaries and omit unsupported explanations and advice from other conditions. Keep the prompt short enough for the existing small-context behavior.

## Verification

The full Python suite passed: **825 tests, 20 skipped**. All three JavaScript suites (stream completion, retrieval UI, guidance UI) passed, and `git diff --check` passed. Thirteen new regression methods cover positive examples and boundary failures. Existing warning tests now distinguish warning classification from evidence sufficiency.

Exact replay of the ten latest captured model drafts is retained in [replay.json](../../tests/evals/emergency_advice/baselines/grounding-2026-11-26/replay.json). It binds the unchanged input capture and relevant code with SHA-256. Original captures and assessments are unchanged. [Scoped source snapshots](../../tests/evals/emergency_advice/baselines/grounding-2026-11-26/scoped-sources.json) show current English, Portuguese and Spanish retrieval with Kiwix disabled.

All ten historical drafts remain blocked. Two recorded false failures are corrected: citation attachment in English pressure trial 3 and mandatory CPR conditions in Portuguese trial 1. Other blocking reasons remain. Seven drafts gain unsupported-explanation findings; two gain cross-condition warning-cluster findings (one overlaps). This is more accurate validation, not evidence of improved generated answer quality or reduced overall withholding. The original displayed fallbacks were not regenerated or rescored.

## Review and limits

Reviewed correctness, readability, module boundaries, security and performance. The new support logic is separate from the existing action rules, uses supplied evidence only and adds no network or installation operations. Source selection copies metadata rather than modifying guide files. Work is bounded by the existing answer/context sizes; no performance benchmark was run.

These are development regressions, not an independent holdout. Causal checks cover listed patterns, warning checks cover a recurring cluster, and section selection covers labelled local guide blocks. Unknown claims, nuanced causal meaning, unsupported quantities, arbitrary foreign-condition prose and unfamiliar negation still require review. `other_claims` remains `unverified`; no general semantic or clinical certification is claimed.

Next: run fresh multilingual model generations, inspect actual usefulness, unsafe instructions, citation support and unnecessary withholding, then repeat with Kiwix enabled. No standalone installation update, commit or push was performed for this follow-up.
