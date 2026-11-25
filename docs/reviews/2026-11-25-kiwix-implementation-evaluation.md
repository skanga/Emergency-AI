# Kiwix repair: implementation and evaluation

Date: 2026-11-25. Branch: `fix/kiwix-retrieval`. Worktree: `/tmp/emergency-ai-kiwix-repair`.

**The broader relevance targets remain unmet. After the initial evaluation, the user authorized merging the incremental improvement once the local-guide regression was fixed. Server restart and clinical reliability approval are separate from this merge.**

## Pre-merge regression repair

A comparison against main exposed a genuine regression despite the earlier passing tests: local-guide eligibility depended on literal library search phrases. For example, `heat stroke` did not recognize the local `Heatstroke and heat exhaustion` heading. Generic headings also hid useful water disinfection, generator, food-storage and flood-cleanup guidance.

Local evidence now uses the existing configured topic vocabulary. Sections with generic headings can establish their topic from their content; a heading identifying a different emergency still prevents an incidental symptom mention from promoting that section. Personal-document handling and age/consciousness checks remain in place. Native library search and library relevance rules were not loosened.

Five real-guide cases failed before the repair and passed afterward. The final suite ran **395 tests, with 16 skipped and no failures**; both Node suites passed. All 46 original knowledge files retain their hashes. The repeated 59-case live retrieval evaluation supplied library context for **21/22** original API cases, had no context-fitting errors or blocked responses, and retained **3/30** annotated target matches. Its p95 retrieval plus prompt fitting was 0.862 seconds. Full local results: `/tmp/emergency-post-local-fix-eval.json`.

The measurements below and the linked compact fixture describe the earlier checkpoint; they remain historical evidence. The merge is an incremental improvement, not a claim that the broader quality or clinical review targets have passed.


## Measured results

| Check | Result |
|---|---|
| Original API questions with a library passage in final fitted context | 21 / 22, versus 0 / 22 in the saved baseline |
| Original cases including electrical browser case | 22 / 23 with a library passage |
| Archive identity errors in the frozen evaluation | 0 |
| Frozen natural-language cases | 59: 23 original, 24 held-out, 12 negative/ambiguous |
| Inspected target sections matched in final context | 3 / 30 annotated cases (10%) |
| Annotated EN / PT / ES target matches | 3 / 18; 0 / 6; 0 / 6 |
| Cases still missing target-section annotations | 29 |
| Retrieval plus prompt-fitting p95 / maximum | 0.806 s / 1.169 s in the final run |
| Existing-backend token fitting | Exercised for all 59 cases; no generation |
| Local knowledge preservation | All 46 original files retain identical paths and SHA-256 hashes |
| Medical PDF collection | 12 documents; 3,174 pages examined; 1,732 usable passages; 1,442 excluded pages; no document failures |

A target-section miss can mean the pipeline chose another relevant reference, selected weaker material, or missed the intended coverage. The current annotations do not establish which explanation applies to every miss. These numbers must not be described as 90% recall, 90% precision, or medical reliability. Human passage relevance and answer-safety labels remain pending. The chemical-water original case did not receive a library passage; adding a citation regardless of applicability is not the objective.

The timing run uses one engine instance, starting with an empty HTML passage cache and then reusing it. It is not a separate repeated cold/warm latency study. A performance defect discovered during evaluation repeatedly scanned every source pair for scope qualifiers; moving the matching-statement check ahead of that scan reduced a controlled 80-passage test from 1.488 s to 0.008 s. Queries and held-out input text were not changed during that optimization.

The compact case/source report is [retrieval_eval_summary.json](../../tests/manual/fixtures/retrieval_eval_summary.json). Full local diagnostic output, including prompt text, is `/tmp/emergency-retrieval-eval-final.json`; it is not committed.

## Implemented protections

- Catalog logical names remain stable selection keys; searches use served archive identities from validated content links. Failures remain distinguishable from successful empty searches.
- EN/PT/ES query planning, follow-up scope, structural extraction, bounded transport, candidate oversampling, relevance filtering and joint local/library context selection operate without a generator.
- Local guides and personal documents remain searchable and read-only. Applicable local procedures are protected; volume of library hits does not establish precedence.
- Reviewed conflict rules bind exact source versions and scope. Automatic numeric conflict detection is deliberately narrow. Unresolved conflicts and omitted preferred corrections withhold advice, including extractive fallback, while preserving original references and notices.
- PDF manifests are data-only; tools are pinned and explicitly prepared. Indexes are archive-version specific. Cancellation and failed refreshes preserve the previous active index. Unchanged documents reuse extraction without changing passage IDs.
- Browser and CLI distinguish native search, article retrieval, PDF coverage, actual inclusion, omissions and disagreements. Section links include their anchors. Notifications survive interrupted answer streams.

## Validation and limitations

Each implementation slice received spec and code-quality review. Regression tests were run failing before repairs and passing afterward. The final integration review found and verified the repair for failed PDF refresh replacing a working index.

The isolated browser on port 8093 was tested with generation disabled. A real choking question included two library passages and separated an omitted passage. Controlled responses verified zero-hit, article-fetch failure, browse-only and interrupted-conflict rendering. The original application on port 8090 remained untouched.

Only Linux x86_64 PDF extraction was exercised, using the pinned official Xpdf 4.06 artifact and a synthetic PDF smoke test, followed by the installed medical collection. Windows/macOS extraction, OCR, complete handling of difficult layouts, independent clinical annotation, and repeated critical-answer generation remain unverified. PDF page passages do not establish that procedures spanning multiple pages are complete. The four other configured document collections are visibly marked as requiring preparation.

The final full suite passed 393 tests with 16 environment/model-dependent tests skipped. Both Node suites also passed. No generated advice was tested in this implementation evaluation because retrieval release gates have not passed.

## Installed archive versions

- `wikipedia_en_medicine_maxi_2026-10`
- `wikem_en_all_maxi_2020-06` (archived)
- `appropedia_en_all_maxi_2026-02`
- `energypedia_en_all_maxi_2026-06`
- `ifixit_en_all_2025-12`
- `zimgit-food-preparation_en_2025-04`
- `zimgit-water_en_2024-08`
- `zimgit-medicine_en_2024-08`
- `zimgit-knots_en_2024-08`
- `zimgit-post-disaster_en_2024-05`

## Remaining release work

1. Complete independent target-section and included-passage annotations, distinguishing acceptable alternative references from genuine misses.
2. Improve and re-evaluate relevance on a fresh held-out set where the evidence shows shortcomings; do not weaken the gate or tune the frozen set merely to obtain more citations.
3. Meet the agreed retrieval gates, then repeat critical generated answers three times and review their actions, scope, harmful additions and citation support.
4. Validate remaining offline/platform/coverage scenarios, then perform the controlled rollout and live smoke tests. These remain quality follow-ups after the user-authorized incremental merge.

Rollback requires no knowledge migration: keep the original code/settings, ignore the new disposable indexes, and retain the installed archives and local knowledge. No source files need deletion or rewriting.
