# Condition-fix evaluation — 27 November 2026

This records uncommitted working-tree changes based on main `105c294`; `provenance.json` binds the exact production files, model and settings. It does not update the standalone installation. Earlier full-main captures and ratings are unchanged.

## Verification

- Full engineering suite: **919 tests, 20 skipped, no failures**.
- Thirteen focused test methods cover captured failures, qualified drafts, unsafe near-matches, language variants and fallback selection. Disabling the safe-approach predicate caused all three heat-shutoff language checks to fail (mutation detected).
- `historical-replay.json`: all 96 first validation inputs rechecked, including pre-generation fallback inputs. Five formerly released defects are blocked; five qualified drafts are released; other first-input statuses are unchanged. These are validator replays, not newly generated answers.
- Fresh local model run: ten affected scenarios × two trials, including live follow-up history. All 20 displayed answers, rejected drafts and cited excerpts were read. Six generated answers, 14 fallbacks; no notice-only, incomplete or transport-error results.
- All 20 reviews are bound to exact requests, answers and source content. Production hashes were unchanged throughout capture. Raw SSE artifacts remain locally under `/tmp/condition-fixes-live-2026-11-27/run/raw`; portable normalized responses and inspection inputs are preserved here.

## Findings

All 20 responses scored usefulness 3. Both cooking-fire drafts omitted safe heat-shutoff conditions and both flood drafts omitted necessary vehicle conditions; all four were replaced by complete conditional fallbacks. Both seizure answers were useful; fallback integration is independently exercised in EN/PT/ES tests. The captured anaphylaxis interval mismatch is blocked in replay and reappeared safely withheld in live generation.

The quality screen **still fails**: one generated hypoglycemia answer says repeat carbohydrate if below 70 **or still symptomatic**, broadening the cited threshold (minor unsafe, major citation finding). Five answers have minor citation gaps, mainly explanations exceeding supplied passages. Two acceptable core answers were unnecessarily withheld (CPR citation distance and combined juice/carbohydrate evidence); two further withholding judgments remain uncertain. These are explicit remaining tasks, not waived checks.

The five historical qualified drafts now pass, with unsafe mutations still blocked. This does not mean every paraphrase passes or every released claim is verified. The new run is targeted English generation; multilingual unit/fallback tests do not replace native-language model review. No independent clinical review or complete new 96-response evaluation is claimed.

## Files

- `run.json`, `inspection.json`, `capture-manifest.json`, `provenance.json`: exact capture and evaluation inputs.
- `reviews.json`, `review-notes.json`, `summary.json`: bound manual assessments and counts.
- `historical-replay.json`, `verification.json`: replay outcomes and verification record.

This directory is developer evaluation evidence; `tests/` is excluded from installation archives through `.gitattributes`.
