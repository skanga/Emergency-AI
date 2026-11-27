# Actionable fallback and applicability fixes

The four requested improvements are implemented with bounded regression coverage. This is a reviewed improvement, not a general clinical-safety certification. No original knowledge files were changed; the standalone installation and its engines were not upgraded or restarted.

## Behavior

- **Conflicting bleach sources:** numerical water-treatment disagreements retain their unresolved status and exclude treatment instructions. A separately authenticated safe-supply unit can still recommend safe bottled water and warn that chemical contamination cannot be fixed by boiling/disinfectant. This does not choose a bleach dose, average competing instructions, or permit boiling around an ambiguous conflict. Unknown conflicts, policy errors, directly disputed sources, and altered catalog content remain blocked.
- **Alone after snakebite without phone service:** the fallback now covers signaling with available whistle/light/mirror, asking anyone reached to summon rescue, minimal movement when help can reach the person, and a last-resort known-safe-route branch. No universal waiting time or safe walking distance is invented. Helpers carrying the person are now explicitly conditional on helpers being available. Regional compression/washing protocols are not generalized.
- **Tourniquet applicability:** removed the catalog's invented mandatory-training prerequisite. The cited Red Cross article describes training as ideal and warns against delaying life-saving care. Life-threatening limb bleeding, commercial-device instructions, joint avoidance, tightening until bleeding stops, no loosening, and emergency help remain. IV insertion remains outside lay guidance. A generated answer cannot silently drop a training restriction from a different cited source or cite an equipment inventory as a procedure.
- **Less unnecessary withholding:** bounded valid CPR paraphrases now recognize gasping/breathing abnormally while retaining the AND condition; Portuguese `de` is no longer mistaken for `dê`; a tourniquet heading can retain its immediately following cited condition; last-option/known-safe-route paraphrases are accepted. Counterexamples with missing, negated, or OR conditions remain blocked. Whole-draft rejection is still conservative and does not establish that every blocked draft needed withholding.

The catalog has 25 units: two added, three revised, and 20 unchanged. [Source mappings and editorial limits](../references/guidance-sources.md) distinguish checked primary references from independent clinical review.

## Fresh evaluation and discovered failures

[Preserved evidence](../../tests/evals/emergency_advice/baselines/actionable-2026-11-27/) contains complete run results, supplied passages, evaluation-only draft captures, bound reviews, provenance hashes, and final-validator replay.

| Stage | Captures | Displayed outcomes | Agent quality review |
|---|---:|---|---|
| Candidate EN/PT/ES, two trials per case | 20 | 17 fallbacks, 3 generated | 17 useful at level 3; three released failures retained; screen fails |
| Final-code confirmation of affected English/Spanish cases, two trials each | 6 | 6 fallbacks | All useful at level 3; no unsafe instruction or citation error identified; two withholding judgments uncertain, so screen incomplete |

Eight water cases in the candidate run stopped generation because of source conflicts and composed fallback guidance. The other 12 candidate cases and all six confirmation cases completed model generation. These are not 26 independent final-revision passes. The candidate run predates the last repairs, and its failure ratings are not overwritten by replay.

The candidate run exposed three consequential releases:

1. Spanish `sangra mucho` missed the bleeding topic, retrieved unrelated kit material, and allowed a generated IV procedure for an untrained person. Added bleeding inflections and made explicit invasive-IV checks independent of successful topic routing.
2. Another Spanish bleeding answer used an equipment inventory to support a tourniquet procedure. Added the observed placement verb to procedure matching and preserved an isolated inventory-citation counterexample.
3. A Spanish snakebite answer allowed movement when symptoms worsened, losing the source's last-resort requirement. Extended the observed movement forms and added the isolated missing-condition regression.

All three original released drafts are rejected by final-validator replay. All six fresh final-code confirmation responses were completed fallbacks. Their cited catalog units retain the relevant conditions. The final screen is **incomplete**, not green: two bleeding-draft withholding judgments remain uncertain because procedural context appears outside individual action sentences and broader explanatory claims were not independently adjudicated. The generated model still produces unsupported claims; useful fallback output is part of the quality improvement.

The four exact English request pairs against the prior broad baseline improved as follows (one historical trial, not a causal/statistical claim): bleach conflict usefulness 1→3; unknown bleach 1→3; lone snakebite 2→3; bleeding usefulness remains 3 while the prior major training/applicability citation error is absent from the displayed fallback. Original historical captures and reviews remain unchanged.

An earlier eight-case development run and an interrupted run with incorrectly copied language metadata remain under `/tmp/actionable-quality-2026-11-27-r2` and `/tmp/actionable-quality-final-2026-11-27`. They are not counted in the table. A harness attempt with a missing trial key was corrected before these recorded runs. The repository now contains the reusable inspection wrapper and corrected multilingual manifest, so reproduction does not depend on those temporary scripts.

## Verification

- Failing-first regression tests cover conflict alternatives, fail-closed policy behavior, disputed supply sources, EN/PT/ES fallback composition, source training restrictions, CPR conjunctions, Portuguese prepositions, heading scope, lone movement conditions, Spanish routing, invasive IV instructions, and inventory/procedure citation separation.
- Final full suite: **906 tests run, 20 skipped, no failures** (`python3 -B -m unittest discover -s tests`). Skips include environment-dependent/native checks; this is not new native installation validation.
- Both review files pass the ordinary eval runner's answer/source/rubric bindings. Final replay is recorded separately from original displayed outcomes.
- `git diff --check` passes. No frontend or installation behavior changed.

Reproduce with [evaluation instructions](../../tests/evals/emergency_advice/README.md#actionable-fallback-follow-up). New evaluation assets are under `tests/`, already excluded from installation archives by `.gitattributes`.

Remaining limits: general semantic validation, arbitrary wording, regional transfer and independent clinical/native-language adjudication remain incomplete. Safe-supply fallback cannot manufacture water when none is available; lone snakebite has no universally safe self-rescue decision. Do not interpret the focused improvement as a whole-suite model-quality pass.
