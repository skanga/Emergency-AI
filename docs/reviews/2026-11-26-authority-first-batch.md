# Authority first batch: source, installation and answer checks

Six scoped English editorial summaries are added under `knowledge/authorities/`: IFRC scene safety, WHO CFAR handover, CDC water, FEMA evacuation, FoodSafety.gov refrigerated food, and WHO snakebite transport. Three full PDF originals are available through an explicit verified download command for offline reading. They are not automatically indexed. This is a curated first slice of the recommended documents, not full-manual retrieval coverage.

## Source and extraction checks

Official publisher URLs, editions, audiences, jurisdictions, locators, rights notes, summary hashes and verified artifact sizes/hashes are in [the catalog](../../config/authority-documents.json). Hashes bind observed bytes; they are not publisher signatures. The three downloaded PDFs were verified a second time through the application downloader, including an offline reuse check with network functions disabled.

| Original | Total PDF pages | Pages accepted by existing layout filter | Activation |
|---|---:|---:|---|
| IFRC 2025 | 594 | 437 | Reviewed scene-safety summary only |
| WHO CFAR | 12 | 1 | Reviewed handover summary only |
| FEMA 2020 | 29 | 7 | Reviewed evacuation summary only |

Extraction ran with existing Xpdf 4.06 on Linux x86_64. An accepted page is not proof of correct semantic extraction. WHO handover PDF page 9, FEMA PDF page 17 and IFRC PDF page 115 were rendered and visually compared with their extracted/source sections. The original CFAR clinical procedures are deliberately not activated for lay-user answers. No new PDF tool or dependency was added.

CDC fact-sheet/supporting-page and FoodSafety.gov raw downloads returned HTTP 403 with both urllib and curl in this environment. Their official content was available through web retrieval and reviewed there. No binary hash or successful direct-download claim is recorded for them. WHO snakebite HTML was downloaded for audit, but is mutable and is not offered as a pinned binary. Its selected first-aid/transport material is summarized with explicit boundaries.

The IFRC original's noncommercial terms and WHO document redistribution uncertainty remain explicit. The software MIT license does not relicense those original files. No original PDF or raw webpage is bundled in Git or installation exports.

## Application and installation checks

- Six summaries load through the existing Markdown section parser and retrieval ranking; complete conditions and references stay in one section.
- A separate managed folder is necessary: the standalone upgrader deliberately excludes personal `knowledge/extra/` files. Tests assert that new summaries are managed and personal files remain protected by the existing upgrade suite.
- Source `language` is explicitly English even when searched through PT/ES; these are not translations. The summaries remain visible in all interface languages, using the existing additional-document presentation.
- All 45 original EN/PT/ES guide Markdown files are byte-for-byte unchanged. Kiwix files and the standalone installation were not modified.
- ZIP and tar exports include all six summaries, catalog and download helper; exclude all eval assets and downloaded originals. A temporary Git index was used to test uncommitted additions without changing the real index.
- Removing the managed-folder loader with an in-process mutation caused all six source retrieval checks to fail. Restoring it passes. The captured floodwater boundary test failed before the vocabulary correction and passed afterwards, with a plain-flood control.
- A local-only evaluation exposed a runner bug: API status legitimately returns `kiwix: null`; the runner assumed a dictionary. A failing regression test verifies the small null-handling fix.

## Actual answer evaluation

The initial run used eight versioned development prompts twice each, with Kiwix disabled to isolate local-source behavior. All 16 displayed answers and their supplied passages were read and rated against the four-dimension rubric. No baseline comparison or statistical improvement claim is made.

| Run | Captures reviewed | Useful ≥3/4 | Major unsafe findings | Major citation findings | Screen |
|---|---:|---:|---:|---:|---|
| Initial batch | 16/16 | 12 | 2 | 2 | Fail |
| Chemical-water routing correction, selected repeats | 3/3 | 3 | 0 | 0 | Selected-set pass |

The initial set produced 14 generated answers, one fallback and one withholding notice. There were no invalid numeric citation IDs. Minor citation overreach occurred in 12 answers; syntactic citation validity is not semantic support.

The initial chemical-water prompt used the compound word “floodwater.” The planner matched flooding but not water contamination, missing the CDC passage. One answer gave irrelevant flood fallback; another added unsuitable plastic-bag protection around gasoline. Adding “floodwater” to the existing water-plus-chemical symptom pattern admits the CDC evidence and retains normal flood routing when no chemical is mentioned. All three exact-request repeats then produced complete, source-backed chemical-water fallback rated 4/4 with no identified safety or citation defect. The rejected drafts remain hidden and are not independently assessed. These repeats use the existing chemical-water fallback, not a newly certified CDC procedure.

Remaining observed problems:

- One snakebite answer invented an exception to WHO's arterial-tourniquet prohibition and conflated it with pressure immobilization. This is a major safety/citation finding despite correct advice at the start of the answer.
- One handover answer was withheld without useful fallback. The hidden draft cannot be judged from validation reasons alone.
- Some answers added unsupported details, broad food-discard claims, region-specific bite washing, or unqualified carrying alternatives. Broad queries also admitted unrelated local passages.
- These failures remain in the versioned evidence. The whole-suite quality gate is still open; no new full-suite or multilingual clinical evaluation was performed.

Model: Qwen_Qwen3.5-9B-Q4_K_M.gguf on the existing llama.cpp service, context 8192, output limit 2048, reasoning disabled. Effective catalog sampler settings were temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5, repeat penalty 1. An earlier test accidentally selected the generic OpenAI backend, allowing reasoning to consume the limit; its one completed incomplete capture is preserved separately and excluded from the 16-answer screen with that reason recorded. Interrupted attempts are listed in provenance, not counted as successes.

Evidence: [initial report](../../tests/evals/emergency_advice/baselines/authorities-2026-11-26/initial-report.md), [selected-repeat report](../../tests/evals/emergency_advice/baselines/authorities-2026-11-26/chemical-followup-report.md), [provenance](../../tests/evals/emergency_advice/baselines/authorities-2026-11-26/provenance.json). Reviews are primary-agent judgments, not clinician certification or an independent holdout.

## Final regression verification

`python3 -B -m unittest discover -s tests`: 748 tests run, 20 skipped, no failures. `node --check web/app.js`, `node tests/test_guidance_ui.js` and `node tests/test_stream_completion.js` passed. All 19 completed review bindings validate against the unchanged authority-case rubric. Native Windows/macOS execution and CI are not run for this uncommitted branch. The isolated evaluation server was stopped; installed services remain unchanged.
