# Multilingual safety-gap fixes

Implemented the gaps identified in the fresh steps 3–4 evaluation. No installed application, model, library or original local guide was modified.

## Changes

- Oral water instructions now enter the existing awake-and-safe-swallowing checks and cited-evidence checks. Recognition covers the captured English, Portuguese and Spanish verbs, including Spanish `ofrézcale`. Portuguese `capaz de engolir` and Spanish `capaz de tragar` are recognized with their negated forms. Topical washing and flood/water-treatment prose are excluded by matching intake actions rather than the word water alone.
- Pressure-bandaging checks recognize the captured Spanish verb inflection and Portuguese/Spanish noun-first phrases. The local-swelling condition reversal is explicitly rejected, including when the question supplies an Australian location. Unknown-region rejection alone is not treated as sufficient protection.
- Consecutive bullet items inherit a directly preceding prohibition heading, with scope ending at other prose or a new heading. This applies to both claims and source evidence. An unrelated prohibition cannot authorize a later instruction.
- “Especially when” emphasis does not turn a prohibition into an exception. Actual exceptions remain blocked. The captured scoped danger explanation is recorded as an unverified warning, not positive advice or verified evidence.
- The bounded repeated-citation grammar accepts plain coordinated verbs and parenthetical tourniquet wording. It still rejects causal explanations and extra claims as citation donors. Unsupported “support you” alternatives cannot borrow stretcher evidence.
- The versioned snakebite fallback now gives helpers/stretcher transport, stillness, urgent care, the arterial-tourniquet prohibition and breathing monitoring in all three languages. Its reference and content hash were updated against [WHO Treatment, Box 1](https://www.who.int/teams/control-of-neglected-tropical-diseases/snakebite-envenoming/treatment), checked 2026-11-26. The existing conditional approach to pressure bandaging remains.

## Verification

Twelve new regression tests cover the preserved counterexamples and positive/negative controls. The initial nine tests produced 20 failing subcases before implementation. Further tests exposed the negated-swallowing variants, unsupported assisted-transport alternative and region-independent swelling reversal before those fixes.

The complete suite passes **794 tests, 20 skipped**. JavaScript guidance/streaming checks and `node --check web/app.js` pass. `git diff --check` passes. Validation was local Linux; no native-platform CI or deployment was performed.

[Exact replay](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/gap-fixes-replay.json) binds the pre-fix drafts and new code hashes. All three previously passing ablation probes now fail: the Spanish swelling inversion gets `snake_compression_condition_unsafe`; both water-condition omissions get `oral_intake_prerequisites_missing`. Rejection no longer depends on the removed unrelated opening clauses.

The older Portuguese draft that previously passed now fails source support for its water instruction: the draft includes safe swallowing, but its cited local passage mentions only consciousness. Its tourniquet prohibitions remain supported. The old capture and review are preserved; the updated regression test separates those facts rather than claiming the entire draft is still acceptable.

Review checked citation identity and rendering, prohibition scope boundaries, negative swallowing, source-object matching, condition preservation and fallback integrity. No new dependencies or production draft logging were introduced. These remain bounded pattern checks, not general semantic or clinical certification.

## Model-backed follow-up

An interim ten-request run started before the final region-independent swelling guard was added. It is retained as `gap-fixes-interim-inspection.json` and must not be presented as final-code validation.

The [final-code capture](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/gap-fixes-final-inspection.json) and [bound per-case review](../../tests/evals/emergency_advice/baselines/snakebite-2026-11-26/gap-fixes-final-review.json) record a separate ten-request repeat: six English, two Portuguese and two Spanish. All ten generations completed normally. All recorded code/catalog hashes match the final worktree; all 18 draft/fallback validation calls reproduce exactly.

- **Two generated answers displayed**, both English: pressure trial 2 and transport trial 3. Both provide useful direct help. The prohibition introduction visibly gains its repeated citation. Unsupported causal explanation and vague “similar support” wording prevent a clean grounding pass.
- **Eight answers used the improved fallback.** Each now includes assisted stretcher transport, urgent care, stillness, the arterial-tourniquet ban and breathing monitoring. The displayed citations match the admitted versioned passage. No affirmative unsafe instruction was identified in the inspected displayed outputs; this is not clinical certification.
- **Unnecessary withholding remains.** New compound/adjective variants and Portuguese `puder engolir` wording expose further parsing limits. Citation policy also continues to reject useful uncited introductions. These are preserved in the review rather than counted as safety successes.
- **New coverage limits remain.** Wheelchair/arbitrary-device and Spanish dragging alternatives are not independently recognized by the method check. The dragging draft was withheld for a separate CPR prerequisite failure. Spanish `Ofrece` is outside the current water-action forms. Whole-draft blocking does not prove those particular clauses were detected.

Compared with the immediately preceding run, generated display changed from 0/10 to 2/10 and fallback content directly answers transport questions. The samples and catalog inputs differ; these counts do not establish a statistical or causal improvement in generation quality. The targeted regressions are fixed, but the broader answer-quality screen still does **not** pass.

Next work should retain these new language/method variants as adversarial fixtures, address their scope and support checks, and then broaden to Kiwix-enabled evaluation. Production installation, commit, push and merge remain untouched.
