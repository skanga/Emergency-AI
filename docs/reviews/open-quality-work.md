# Open quality work

Updated 2026-11-27 against main `105c294`. Integration is complete through [PR #7](https://github.com/skanga/Emergency-AI/pull/7); the earlier proxy/quality work was merged in [PR #6](https://github.com/skanga/Emergency-AI/pull/6). That merged revision contains 25 catalog units; the current working tree adds a 26th, seizure first aid. All PR #7 CI checks passed, including Linux, Windows and macOS ARM/native checks. The standalone installation was not updated by those merges.

The release criterion is a reviewed improvement over main, not perfection. No whole-suite answer-quality pass or independent clinical approval is claimed. [Evaluation results and evidence](../../tests/evals/emergency_advice/RESULTS.md) preserve failures separately from later validator replays.

## Next work

- [x] Repeat the full-suite model-backed evaluation on main `105c294`, including rejected drafts: **96/96 captured and reviewed**, 92 usefulness ≥3, three major unsafe and four major citation findings. [Evidence and comparison](../../tests/evals/emergency_advice/baselines/full-main-2026-11-27/README.md). Screening still fails.
- [x] Repair the captured cooking-fire safe-approach, flood trapped-vehicle and anaphylaxis repeat-timing/source failures. Historical replay blocks all five previously released defective drafts, including the lesser flood case. Full engineering suite: 919 tests, 20 skipped; targeted live evaluation: 20 reviewed answers. [Working-tree evidence](../../tests/evals/emergency_advice/baselines/condition-fixes-2026-11-27/README.md). A new complete 96-response model run remains outstanding.
- [x] Add CDC-based seizure fallback in EN/PT/ES, including emergency-call/no-restraint/no-mouth-object help. Runtime fallback integration is tested in all three languages; both fresh English seizure answers were useful.
- [x] Release the five captured qualified burn, hypoglycemia, CPR-boundary and repeat-injector drafts through bounded citation/condition checks. Unsafe near-matches and region-dependent snake washing remain blocked.
- [ ] Address remaining false-positive wording found in the fresh targeted run (CPR prohibition separated from its citation; combined juice portion/carbohydrate evidence). Two fresh withholding judgments remain uncertain.
- [ ] Repair the fresh hypoglycemia repeat instruction that adds “or remains symptomatic” to the below-70 threshold; investigate unsupported generated explanations and source co-citations. The targeted quality screen still fails despite all 20 answers being useful.
- [ ] Resolve the two uncertain bleeding-withholding judgments in [final confirmation reviews](../../tests/evals/emergency_advice/baselines/actionable-2026-11-27/confirmation-reviews.json). Inspect conditions spanning sentences and broader explanations before relaxing any check. Retain negative controls.
- [ ] Obtain independent clinician/first-aid and native-language review of exact catalog hashes and EN/PT/ES wording, then add independent holdout prompts. Agent reviews cannot supply that independence.
- [ ] Annotate the remaining 29 of 59 retrieval cases and included-passage precision independently. Last measured annotated-section matching was 15/30. Proposed 90% recall/precision targets remain unproven, not silently waived as measured results.
- [ ] Investigate new observed evidence/coverage gaps, including handover fallback and unsupported explanatory additions. Known-pattern validation cannot verify all paraphrases, regional protocols, mixed injuries or source conflicts. Preserve useful alternatives and action conditions while adding bounded repairs.
- [ ] Complete physical phone/LAN browser checks, real video playback/codec tests, and genuinely cold filesystem-cache measurements. Native CI and local Chromium checks do not establish these scenarios.
- [ ] Upgrade and smoke-test the standalone installation through [the upgrade procedure](../upgrades.md) when requested; record its deployed identity. Repository merges do not update that installation.
- [ ] Complete the separate [original-guide content review](../../TODO.md). The fallback catalog does not repair every original guide; infant technique, water-treatment limits and hazardous DIY instructions still need review.

## Accepted limits and preserved evidence

Kiwix retains one hostname/port and archive scripts as requested. Archive pages share the app origin, API access and browser storage; isolation is an accepted trade-off, not an unresolved implementation promise. Bounded streaming, same-origin upstream redirects, upstream status preservation, range/HEAD responses and `nosniff` are integrated. Local Chromium checks covered catalog/article search, JavaScript lists, images and a real PDF range response. Physical devices and actual video codecs remain untested.

Source-reference records in [guidance sources](../references/guidance-sources.md) and [action conditions](../references/action-conditions.md), original local knowledge, frozen eval captures, JSON evidence and original failed ratings are retained. Old dated review narratives were removed after carrying forward these open obligations; Git history preserves their details. Historical test counts and historical failed screens must not be presented as current-main results.
