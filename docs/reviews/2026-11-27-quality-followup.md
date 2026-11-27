# Quality follow-up and remaining work

This follow-up fixes bounded regressions and preserves the failed evaluations. It does **not** establish a complete answer-quality pass or independent clinical approval. The existing standalone installation was not modified or restarted.

## Implemented

- Spanish coordinated tourniquet prohibitions accept `No uses … ni …` while affirmative and exception controls remain blocked.
- Recognized limb elevation, vertical positioning and wrist flexion require their own supporting evidence. Different positions and negated evidence cannot lend support; explicit qualifications are retained conservatively.
- Recognized cleaning instructions cannot invent WHO/Red Cross attribution or drop/change the supported regional scope.
- The recorded Crotalus efficacy reversal is checked separately from other hazards. This is a bounded check of that documented conclusion, not a general species/protocol reasoner.
- Additional EN/PT/ES tissue/circulation explanations and pronoun references require matching evidence. Unsupported renal-failure claims in dehydration answers are also checked after a fresh capture exposed one.
- A new NHS-backed dehydration escalation unit provides useful help when a generated recipe is withheld. All three translations pass the actual planner/fallback validator; the previous 22 units are unchanged.

The enduring source records moved to [guidance sources](../references/guidance-sources.md) and [action conditions](../references/action-conditions.md). The stale [retrieval plan](../superpowers/plans/2026-11-24-kiwix-retrieval-repair.md) now distinguishes integrated features, current fixes and outstanding evidence. Reference checks and independent clinical approval are explicitly different.

## Verification

Failing-first regressions cover each new behavior, including valid counterparts. Final verification: **891 Python tests run, 20 skipped, no failures**; all four JavaScript checks passed. Original local knowledge and the original 22 catalog units are unchanged.

[Evidence directory](../../tests/evals/emergency_advice/baselines/quality-followup-2026-11-27/) contains the following:

| Check | Result | Limit |
| --- | --- | --- |
| Original three isolated probes | Correct prohibition passes; unsupported elevation and tissue claim fail | Known wording only |
| Twenty historical drafts | Previously blocked Spanish prohibition answer passes; previously released elevation answer fails | Deterministic replay, not fresh generation or general clinical approval |
| Fresh local/Kiwix snakebite trials | 20 captures reviewed | Interim revision; subsequent fixes have final-validator replay |
| Further snakebite confirmations | 4 multilingual captures, then 1 Spanish positioning capture | Separate revision hashes; selected cases, not a whole-suite repeat |
| Fresh multi-domain run | 32/32 complete captures and bound reviews | One trial; **quality screen fails** |
| Dehydration follow-up | 3 fresh EN/PT/ES captures | EN/PT display escalation fallback; Spanish adds an unsupported diagnosis, retained as a failure and rejected by final replay |
| Operating matrix | 24 checks across 8 scenarios; maximum 0.833 seconds | Client-cold only; no OS-cache flush, physical-device test or statistical p95 claim |
| Retrieval benchmark | 15/30 annotated gold-section matches across 59 cases | 29 unannotated; independent precision unknown; concurrent generation makes timing non-isolated |

There are **60 fresh captures** across these stages, plus historical replays. Do not combine them into a single final-revision pass rate. Draft inspection is evaluation-only and does not enable rejected-draft logging in the app. Compact captures omit bulky duplicate retrieval diagnostics and retain raw hashes; full raw diagnostics remain under `/tmp/quality-followup-2026-11-27`, `/tmp/quality-retrieval-2026-11-27.json` and `/tmp/quality-operating-matrix.json`.

The multi-domain run displayed 5 generated answers, 24 fallbacks and 3 notices. Agent review rated 28/32 useful at level 3; three notices were level 1 and the lone-snakebite case level 2. No major/critical unsafe instruction was identified in displayed answers, but three safety assessments remain uncertain. Citation review found one major applicability error and three minor errors. Eight withholding decisions remain uncertain. Valid numeric citation IDs in all 32 answers do not establish semantic support. See [bound reviews](../../tests/evals/emergency_advice/baselines/quality-followup-2026-11-27/broad-reviews.json) and [summary](../../tests/evals/emergency_advice/baselines/quality-followup-2026-11-27/broad-summary.json).

The new dehydration unit fixes the notice-only fallback gap in selected repeats; it does not retroactively improve the original run's score. The subsequent Spanish kidney-failure assertion was attributed to a passage that only supports escalation. Its failing capture, isolated regression and final rejection remain visible. Final replay records validation decisions separately from what was actually displayed.

## Remaining findings at this revision

The first four items received subsequent bounded fixes and new model-backed evaluation in [actionable fallbacks](2026-11-27-actionable-fallbacks.md). This historical run and its failures remain unchanged.

1. Bleach-source conflicts still produce a notice without a safe-supply alternative. Resolving this requires action-level conflict handling; a new source ID must not bypass the existing topic-wide conflict guard.
2. The snakebite fallback is useful when helpers are available, but does not solve a lone person's transport/help problem without phone service. Do not invent a universal walk-versus-wait rule.
3. The untrained bleeding/IV case cites a training-restricted catalog unit for a tourniquet step. Source applicability remains imperfect. The current Red Cross article describes training as ideal and warns against delaying care; the catalog's stricter boundary is an editorial choice requiring review, not grounds for a blanket untrained-tourniquet prohibition.
4. Bounded matching still misses unlisted diagnoses, explanations and positioning variants, and can withhold valid paraphrases. The supported controls are necessary but not comprehensive semantic verification.
5. Independent clinical/native-language review, independent holdouts, remaining gold annotations, physical phone/LAN testing and real video playback remain outstanding.

The user's acceptance bar is a reviewed improvement over main, not perfection. The above failures remain part of that decision; this report does not label them resolved.

## Proxy integration

The existing proxy work preserves one hostname/port and Kiwix scripts, as requested. Its [compatibility evidence](2026-11-27-kiwix-proxy-validation.md) remains valid for its recorded revision. GitHub Actions passed at `f1ef95e`; these new local changes have not run in remote CI. No PR is open, and merge remains pending the integration decision. Same-origin archive-script access is an accepted design trade-off, not a closed isolation vulnerability.
