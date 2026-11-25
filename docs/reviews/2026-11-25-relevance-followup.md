# Retrieval relevance follow-up

Baseline: main at `f218d9b`. The previous `fix/kiwix-retrieval` branch was deleted locally and remotely after confirming it was merged. Its prepared indexes were retained for this work.

## Changes

- Recognize ordinary EN/PT/ES symptom descriptions, explicit topic changes, plural patient ages and nonmedical word senses. Mixed-context symptoms remain valid even near equipment or recipe words.
- Rank canonical topic articles and applicable first-aid sections ahead of specialist or administrative material. Reject mismatched conditions, population scopes, oral-intake sections for unconscious patients, and nonmedical local-guide homonyms.
- Require concrete context for ambiguous PDF matches. “Flood the wound” and botanical descriptions of flood plains are not flood-emergency evidence. Direct flood first-aid sources remain eligible across wording variations.
- Keep exact duplicate text from occupying multiple context slots. Preserve punctuation and quantities when comparing duplicates. A PDF book title is not treated as a procedure heading.
- Retain local guides, personal documents, source versioning and reviewed conflict precedence. No knowledge-file content or clinical protocol was edited.

## Verified results

| Check | Result |
|---|---|
| Full regression suite | 423 tests run, 16 skipped, no failures |
| Browser JavaScript suites | Both passed |
| Original local knowledge | 46 files, identical SHA-256 hashes |
| Historical exact annotated-section matches | 28/30 (93.3%), up from 3/30 |
| Historical EN / PT / ES matches | 16/18; 6/6; 6/6 |
| Fresh frozen topic/intent checks | 24/24: EN 10/10, PT 7/7, ES 7/7 |
| Original API cases with library context | 19/22 |
| Historical retrieval + prompt-fit p95 / maximum | 0.944 s / 1.011 s |
| Context-fitting failures | 0 |

The 59 historical questions were already observed; their results are regression measurements, not a new unbiased recall estimate. The additional 24 cases were written and frozen before this change. Topic recognition is not passage precision or answer accuracy. No gold target was changed to improve these measurements.

The two exact-target misses are unconscious-infant follow-ups: the supplied section is the applicable unconscious-infant subsection, while the frozen target names its parent. The historical metric remains unchanged rather than counting these as passes.

Library-context count falls from 21/22 to 19/22 because irrelevant material is no longer counted as success. The grease-fire case has no usable evidence; the flooded-road case has local evidence but no usable library passage; the bleach-water case is withheld due to detected unresolved quantity disagreements. No automatic precedence rule was invented to bypass that disagreement.

The compact case/reference evidence is [relevance_followup_summary.json](../../tests/manual/fixtures/relevance_followup_summary.json). Full local reports are `/tmp/emergency-relevance-release-eval.json` and `/tmp/emergency-relevance-release-fresh.json`.

## PDF coverage and limits

All five enabled document collections were prepared on Linux x86_64. Together their reports cover 155 manifest documents and 17,725 examined pages: 9,477 usable page passages and 8,248 excluded pages. Two foraging PDFs in the post-disaster collection failed extraction and remain explicitly reported. No archive or original PDF was changed. Partial extraction, difficult layouts, OCR and cross-page procedure completeness remain limitations; an indexed collection is not a claim of complete coverage.

Prepared indexes and the verified extractor are generated local artifacts, excluded from Git. They are retained in the main checkout for subsequent runs. The server is not restarted by this change.

## Review and remaining validation

Fresh code review found and verified fixes for multilingual evidence rejection, mixed medical/nonmedical context, overbroad refrigeration restrictions, flood-action wording, plural ages, and valid medical usage headings. Final review found no remaining blocker in those corrections.

Independent clinical review, exhaustive source-applicability annotation, and repeated generated-answer safety evaluation remain outstanding. The earlier broader release gate is therefore not claimed as passed merely because exact-section recall exceeds 90%. This is an incremental retrieval-quality improvement under the user's revised merge criterion. Unsupported questions must remain visibly unsupported rather than receive forced citations.
