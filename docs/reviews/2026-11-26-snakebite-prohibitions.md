# Snakebite prohibition validation

The captured `snake_pressure` trial 2 answer invented an exception to WHO's arterial-tourniquet prohibition. This change blocks that saved answer and supplies the existing source-backed fallback when the same draft is passed through the engine. Supported paraphrases remain allowed. It does not establish general semantic correctness or a whole-suite quality pass.

## Root causes and changes

1. Topic routing recognized “snake bit” but not “bitten by a snake” or “snake bite.” The original question consequently had no snakebite topic, bypassing existing pressure-bandage checks and snakebite fallback selection. Added these forms and tested Portuguese/Spanish bite verbs; a snake-plant control remains outside snakebite.
2. The bounded claim validator had no tourniquet family. Added a snakebite-only rule recognizing direct and passive prohibitions, rejecting affirmative instructions and invented exceptions, and requiring the claim's own cited prohibition. An earlier correct warning cannot authorize a later contradiction. Adjacent explicit exception/pronoun clauses are checked on both the answer and source sides.
3. Coordinated negative lists and “even if” prohibitions remain valid. Pressure immobilization retains its separate applicability rule. Unrelated life-threatening bleeding does not activate this guard.

The WHO source was checked on 2026-11-26: [Treatment, Box 1](https://www.who.int/teams/control-of-neglected-tropical-diseases/snakebite-envenoming/treatment). It prohibits tight arterial tourniquets and gives pressure immobilization separate indications. No source document, installed knowledge, or clinical procedure was rewritten.

## Deterministic verification

Twelve new tests cover the exact captured answer, multilingual routing, positive/negative polarity, exceptions, nearby pronouns, own-citation support, source-side exceptions, preserved paraphrases, unrelated bleeding, existing pressure-bandage boundaries, all three fallback languages, and end-to-end fallback without rejected-draft leakage. Tests failed before their corresponding changes. The original 55 claim tests passed before implementation.

The Python suite runs 760 tests with 20 skips and no failures. JavaScript guidance/streaming tests and syntax checks pass. These are Linux checks; native Windows/macOS CI has not run for this uncommitted branch.

An initial restricted-sandbox full run failed because existing server tests could not create sockets. The same suite passed with local socket permission. That environmental failure was not treated as a code regression.

## Captured-answer replay

[Before](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/validation-replay-before.json) and [after](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/validation-replay-after.json) replay the 14 generated answers from the original 16-answer authority run; its fallback and withheld answer are excluded because they are not generated drafts. Display citations were converted back to the model's `[S#]` namespace.

Three previously released snakebite answers are now blocked, including the known major failure. Other answers retain their previous validator result. The other two newly blocked answers include missing action citations/unsupported explanations, so this is not evidence that three harmful answers were prevented. One coordinated-prohibition false positive found during replay was corrected and retained as a regression test. The validator still requires explicit source support for recognized instructions, including warnings in introductory text.

## Live and offline answer evidence

All captures and bound reviews are retained under [snakebite-2026-11-26](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26). Kiwix was disabled to isolate this local-source regression.

| Run | Captures | Result | Interpretation |
|---|---:|---|---|
| Interim live English, 2 cases × 3 | 6 | 1 generated, 5 fallbacks; all usefulness 3/4 | Server loaded the earlier implementation before the last coordinated-list/pronoun/source-context corrections. Not a final-code live run. |
| Final-attempt English, 2 cases × 3 | 6 | All `model_unavailable` fallbacks; usefulness 3/4 | Offline fallback check only. |
| Final-attempt Portuguese/Spanish, 2 cases × 2 | 4 | All `model_unavailable` fallbacks; usefulness 3/4 | Offline multilingual fallback check only. |

The interim generated answer had minor unsupported transport detail and overstated the blanket need for antivenom. No major unsafe instruction was identified in these displayed captures. All fallback instructions matched their cited versioned guidance. Their brevity omits practical carrying details and additional precautions, so they were not rated complete (4/4). Hidden rejected drafts were unavailable; the five validation-triggered fallback reviews mark withholding uncertain. The interim screen is therefore incomplete, not passed. The offline screens pass only their selected displayed-fallback checks.

Both installed services (8090 app and 8091 model) became unreachable before the final attempts. A separate process attempted to run the existing CUDA b12719 runtime and Qwen3.5-9B model on 8191; it exited 139 before producing startup logs or binding the port. No runtime/model downloads, installation changes, or service repairs were performed. Final-code model-backed repeats were subsequently completed after the user restarted the model; see below.

The successful interim model was Qwen_Qwen3.5-9B-Q4_K_M.gguf using llama.cpp, context 8192, output limit 2048, reasoning disabled; effective sampler temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5, repeat penalty 1. The evaluation app ran from the isolated worktree on 8199. Reviews are primary-agent judgments, not clinician adjudication or independent holdout evidence.

## Remaining limits and next verification

These are known-pattern checks. Unrecognized synonyms, distant references, complex conditional prose, and clinical situations combining a bite with a separate bleeding emergency are not comprehensively modeled. The guard is conservative when snakebite applies; it does not prescribe mixed-injury treatment. Diagnostics retain `known_patterns_only` and `other_claims: unverified`. High fallback frequency warrants further false-positive evaluation; blocked counts alone are not quality scores.

The restored-model repeat is complete. Before broadening to the historical suite with Kiwix enabled, investigate the high rejection rate and unsupported transport paraphrases. No whole-suite, multilingual clinical, or causal improvement claim is made here.

## Completed final-code model-backed repeat

After the user restarted the installed model, the final worktree code was loaded into a fresh evaluation server on 8199. Its implementation hashes match `provenance.json`. The model, sampler, context and reasoning settings match the successful interim run. All ten requests completed model generation with `finish_reason: stop`; none used `model_unavailable` fallback. No implementation code was changed during this repeat.

| Cases | Captures | Generated answers released | Validation-triggered fallbacks | Usefulness ≥3/4 | Quality screen |
|---|---:|---:|---:|---:|---|
| English pressure and transport, three trials each | 6 | 2 | 4 | 6 | Incomplete |
| Portuguese/Spanish pressure, two trials each | 4 | 0 | 4 | 4 | Incomplete |

[English report](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/final-live-english-report.md) and [multilingual report](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/final-live-multilingual-report.md) bind each review to its captured answer, request, supplied passages and rubric. All original interim/offline runs remain preserved.

No major unsafe instruction or invalid numeric citation was identified in the ten displayed answers. Both generated transport answers had minor safety/citation concerns: one added a chair alternative, and the other added “support your weight while they move you quickly,” neither established by the cited stretcher guidance. The first also added uncited warning signs and used region-specific washing advice without establishing the location. These additions remain outside the bounded prohibition fix.

The eight fallbacks provide useful, cited stillness and urgent-transport guidance in the requested language, but omit practical carrying details and extra precautions; all answers were rated 3/4 rather than complete. Their hidden rejected drafts were not available for review. Withholding therefore remains uncertain for eight answers, preventing a quality-screen pass. An 80% fallback rate is a reason to investigate false positives, not proof that eight unsafe answers were prevented.

Next work: add evaluation-only capture of rejected synthetic-test drafts (outside production logs and API responses), assess why each draft was blocked, and fix demonstrated false positives without weakening the captured unsafe-exception guard. Then rerun these cases and broaden with Kiwix enabled. The targeted evaluation itself is complete; the quality gate remains open. The temporary evaluation server was stopped, and the user's model and installed app were left running.

## Rejected-draft inspection follow-up

[Inspection complete](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/draft-inspection-review.json) for ten new diagnostic samples: seven blocked, three released. It found both correct safety rejections and parsing false positives. The original eight hidden drafts remain unrecoverable. No validator behavior changed during inspection; fixes and renewed quality screening remain open.

## Prohibition-parser follow-up

[Steps 1–2 replay](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/prohibition-parsing-replay.json): negative grammar and warning classification were corrected after the diagnostic inspection. Exact replay removes one unnecessary rejection while retaining the three substantive safety failures. The updated suite passes 772 tests with 20 skips. Earlier model runs remain historical evidence for the prior implementation; fresh model-backed screening of this follow-up remains open.
