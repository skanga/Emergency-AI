# Kiwix Retrieval Repair Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Checkboxes track completion. Implementation is in progress on branch `fix/kiwix-retrieval` in `/tmp/emergency-ai-kiwix-repair`. The running service has not been changed.

**Goal:** Make selected offline libraries contribute relevant, attributable, complete passages to emergency answers, and make unavailable or unsuccessful retrieval visible.

**Architecture:** Retain Kiwix as the archive server and native search engine. Introduce a bounded pipeline for query planning, candidate retrieval, section extraction, relevance ranking, and joint guide/library context selection. Add a separate persistent local index for document collections whose PDF contents are not exposed through native Kiwix search.

**Tech Stack:** Existing Python standard library, unittest, browser JavaScript, local Kiwix, and existing local model backends. PDF preparation uses a separately packaged, pinned text-extraction executable; serving ordinary HTML references must not require that executable, pip, an embedding model, or internet access.

## Implementation record

- Baseline: 289 tests passed, 16 skipped. Implementation remains isolated on `fix/kiwix-retrieval`; the running service and main checkout are unchanged.
- `edc6705`: reviewed archive identity repair and request-local search outcomes.
- `474bc91`: scoped multilingual query planning and structural HTML passages.
- `f27dc9a`: bounded PDF preparation and versioned document indexes.
- `94e7988`: bounded passage retrieval, relevance filtering and diagnostics.
- Subsequent reviewed changes add conflict policy and context protections, browser/CLI reporting, evaluator, source anchors, document capability states, and preservation of the previous index on failed refresh. Automatic conflict detection is limited; unresolved detected conflicts withhold all advice rather than attempting to derive shared safe actions.
- Final regression run: **393 tests passed, 16 skipped**, plus both Node suites. Isolated browser checks cover success, zero hits, fetch failure, browse-only and interrupted conflict notices.
- Frozen evaluation: 59 cases; library context for **21/22** original API cases (22/23 including electrical), but only **3/30** annotated target-section matches. Another 29 cases lack gold annotations. Independent passage precision and answer safety remain unverified. Retrieval plus prompt fitting p95 was 0.806 seconds, maximum 1.169 seconds; this was not a separate cold/warm benchmark.
- Prepared the medical document collection: 12 documents, 3,174 pages, 1,732 usable passages, 1,442 excluded pages. Only Linux x86_64 extraction was exercised.
- All 46 original local knowledge files retain their paths and SHA-256 hashes. Generated indexes and tools are separate ignored artifacts.
- **Release gates have not passed.** Generation evaluation and rollout were not performed. Remaining task checkboxes are not a declaration of completion; annotation, relevance improvements, platform/offline scenarios and answer review remain open.
- Detailed results and remaining work: [implementation evaluation](../../reviews/2026-11-25-kiwix-implementation-evaluation.md).

## Scope and decisions

This work covers the complete path from library discovery to passages actually included in model input, including browser and CLI reporting, setup, cache lifecycle, and regression evaluation. Fixing the catalog identifier alone is an interim repair, not completion.

Three approaches were considered:

| Approach | Benefit | Limitation | Decision |
|---|---|---|---|
| Correct archive names and retain the current pipeline | Small, independently testable repair | Diagnostic replay still produced zero Kiwix passages for all 22 questions | First delivery only |
| Repair native search and add local PDF indexing | Works without an additional model; avoids indexing entire encyclopedias; addresses every observed failure stage | Requires query, passage, and ingestion work | Recommended |
| Reindex every archive with embeddings and a reranker | Potentially stronger semantic retrieval | Large preparation cost, storage and runtime dependencies; relevance still needs evaluation | Defer until evidence shows the repaired lexical pipeline is inadequate |

Keep generation on the existing model. Do not broaden the question into unrelated emergencies, introduce cloud services, silently enable deselected libraries, change guide medical content, or treat citation presence as proof of medical correctness. Emergency protocol revision is a separate workstream, although answer-quality regressions must block this rollout.

The existing standard-library serving path remains supported. PDF extraction is a preparation capability with an explicit availability state. A library whose documents have not been indexed remains readable and is labeled accordingly; it must not be represented as searchable evidence.

## Local knowledge preservation and conflicting evidence

Preserving files and preserving their contribution to answers are separate requirements.

- Treat `knowledge/en/`, `knowledge/pt/`, `knowledge/es/`, and `knowledge/extra/` as read-only inputs to retrieval and indexing. No refresh, migration, cleanup, or rollback may overwrite or delete those files. Generated indexes and caches live in separate directories and are disposable.
- Continue searching local knowledge on every request, including when Kiwix is enabled. Kiwix failure must leave local retrieval operational. Personal documents remain eligible under their existing language behavior.
- Preserve a directly applicable local procedure as the initial answer basis when it passes relevance and scope checks and no reviewed policy supersedes it. Kiwix adds supporting evidence, missing details, or an explicit correction. A larger number of library matches must not crowd out an applicable local procedure.
- Do not blindly reserve space for irrelevant local results. Unsupported or obsolete local guidance must not be treated as correct merely because it is local; an explicit, traceable correction can take precedence without modifying the original file.

Apply the following conflict policy before final context selection:

1. **Establish applicability first.** Distinguish population, age, jurisdiction, substance/concentration, equipment, and stated conditions. Advice for different conditions is not automatically a contradiction. Never combine incompatible procedures into one answer.
2. **Distinguish source location from authority.** Local and Kiwix are storage locations, not reliability levels. Compare identifiable issuing authority, original guidance/revision date, scope, and explicit supersession. An archive download date is not a clinical revision date. Unknown authority or date stays unknown.
3. **Use reviewed precedence when available.** Store explicit source-version and topic/scope precedence in `config/source-policy.json`, with rationale and review metadata. An identified authoritative revision may supersede an older local excerpt. Do not infer supersession from a newer filename, a search score, model confidence, or a majority of duplicate sources. Personal notes can establish user-specific operational facts but are not automatically clinical authority.
4. **Surface unresolved material disagreements.** Retain both complete relevant passages and their provenance. Say that the references disagree, identify the disputed point, and avoid choosing a hazardous procedure or quantity without sufficient support. Do not average doses, merge incompatible steps, or present two dangerous alternatives as a menu for an untrained user. Give independently supported immediate safety actions while directing the user to appropriate professional help when available.
5. **Keep conflict state through context fitting.** Preserve the dispute record and both passages when they fit. If they cannot fit, emit an application-generated conflict notice and withhold the contested procedural recommendation; dropping the disagreeing source must not make the answer appear settled. Preserve links for inspection.
6. **Make corrections visible.** If reviewed precedence resolves a disagreement, explain which source/version is followed and why, and cite it. Retrieval never rewrites the original local guide; source maintenance remains a separate reviewed change.

Conflict detection cannot guarantee recognition of every contradiction in free text. Use reviewed known-conflict rules and scoped checks for conspicuous numeric/procedural disagreements; instruct generation to flag additional disagreements it encounters. Model-produced flags are advisory and cannot establish source authority. Report detection limits and test missed-conflict cases rather than claiming a universal automatic medical arbiter.

## Established baseline

On the installed ten-library configuration:

- All ten catalog names sent as `books.name` returned HTTP 400, `No such book`.
- All ten served identifiers obtained from catalog HTML content links returned HTTP 200.
- With identifiers corrected in an isolated client, 19 of 22 original questions returned no candidates. The other three returned four articles, all above the 20,000-character extraction limit. No Kiwix passages survived.
- Manual short queries returned 66 candidates. Thirteen exceeded the extraction limit; 40 passed existing extraction/relevance checks; 31 of those were omitted by the 7,000-character guide-first budget. Only nine questions retained any Kiwix text, including irrelevant passages.
- The medical document collection loads a JavaScript database containing 12 PDF references. Its initial HTML does not contain those documents.
- Thirty-six focused existing tests passed despite the live integration failure.

Original evidence is in `/tmp/emergency-kiwix-diagnostic/` and `/tmp/emergency-advice-review/`. Task 1 moves the small, necessary fixtures into the repository so verification does not depend on temporary files. Do not commit entire downloaded reference articles, archives, or generated model output collections unnecessarily.

## Target data flow

1. Resolve selected catalog entries to current served archive identities and capabilities.
2. Build a query plan from the current question, relevant recent user context, and source languages.
3. Search selected native libraries and any prepared document indexes within a shared deadline.
4. Fetch an oversampled candidate pool and extract complete, attributable sections.
5. Reject incidental matches, incompatible topics, duplicate content, and unusable passages; refill within the remaining request budget.
6. Rank relevant guide and library passages together, preserving scope and source dates.
7. Fit complete passages to the actual model input allowance, reserving generation space.
8. Assign citation numbers and emit source inclusion status and retrieval diagnostics.
9. Generate, or show an honest extractive fallback when the model is unavailable.

All stages must operate with `use_llm=false`. Query preparation must not need the generator model or contend with model switching.

## File ownership and contracts

| File | Responsibility |
|---|---|
| `app/kiwix.py` | Catalog parsing, same-service URL validation, native search and article transport |
| `app/retrieval_types.py` — new | Shared internal dataclasses for libraries, queries, candidates, passages, and diagnostics |
| `app/query_planner.py` — new | Context-aware EN/PT/ES query construction and bounded alternatives |
| `config/retrieval-topics.json` — new | Reviewed multilingual topic phrases and scope vocabulary; no treatment instructions |
| `app/passages.py` — new | Structural HTML/text section extraction and provenance |
| `app/retrieval.py` — new | Deadline, oversampling, passage relevance, deduplication, and joint source selection |
| `app/source_policy.py`, `config/source-policy.json` — new | Scoped reviewed source precedence and unresolved-conflict records, independent of retrieval scores |
| `app/document_index.py` — new | Collection discovery, prepared PDF passage index, incremental updates and querying |
| `app/engine.py` | Answer orchestration and final model context accounting |
| `app/knowledge.py` | Existing guide retrieval; reuse useful BM25 machinery without changing unrelated search behavior |
| `app/server.py`, `emergency.py` | Additive API/SSE diagnostics and CLI inspection/preparation commands |
| `web/app.js`, `app/i18n.py` | Library capability, failure, inclusion, and omission messages in EN/PT/ES |
| `app/prepare.py`, `app/startup.py`, `config/settings.json` | Optional extraction capability, settings, and preparation status |
| `config/document-tools.json` — new | Pinned extractor artifacts, checksums, supported platforms, license metadata |
| `docs/technical-reference.md`, `docs/troubleshooting.md`, `docs/downloads.md` | Behavior, settings, preparation, recovery, and limitations |

Internal fields must be explicit:

- `Library`: `catalog_name`, `archive_id`, `served_name`, `content_url`, `title`, `language`, `issued`, `capabilities`.
- `QueryPlan`: `question`, `request_language`, `context_terms`, `topics`, `scope`, `queries_by_language`. Scope includes age group and relevant negated facts when stated; it is not a diagnosis.
- `Candidate`: archive identity, canonical article URL, title, source language, query provenance, native rank, snippet, and source date.
- `Passage`: stable ID, archive identity, article title, heading path, original text, language, source date, URL/anchor or PDF page range, topic/scope signals, and score components.
- `RetrievalDiagnostics`: selected/searched/succeeded/failed counts, bounded per-library error codes, stage timings, candidate/passages counts, rejection reasons, included passage IDs, and final omission reasons.
- `EvidenceConflict`: topic/scope, disputed point, source passage IDs and versions, detection basis, resolution (`unresolved` or `reviewed_precedence`), policy rule ID when applicable, and visible explanation. Never fabricate an authority/date to populate this record.

Preserve existing public source fields (`kind`, `n`, `text`, `link`, `doc_title`, `section`, `context_omitted`) while adding provenance and inclusion reasons. Keep `name` in catalog responses as the existing selection key; do not silently reinterpret saved browser selections as versioned archive IDs. Internal dataclasses are serialized explicitly at the API boundary.

## Execution sequence

For each task: add the specified failing regression first, run it to confirm the expected failure, implement only that task, run its focused checks, then review and commit the task separately. Do not modify the user's running process until the rollout task. Do not commit unrelated files such as `emergency-advice-prompts.txt` or `mcp-server.log`.

### Task 1: Preserve the baseline and create realistic integration fixtures

**Create:** `tests/fixtures/kiwix/catalog.xml`, `tests/fixtures/kiwix/search.xml`, `tests/fixtures/kiwix/articles/`, `tests/fixtures/retrieval/cases.json`, `tests/test_kiwix_contract.py`.

**Modify:** `tests/mock_servers.py`, `tests/manual/README.md`.

- [ ] Preserve the real catalog shape: logical name, UUID, flavour, date, HTML content link, and capability tags. Include the actual distinction between `wikipedia_en_medicine` and `wikipedia_en_medicine_maxi_2026-10`.
- [ ] Make the mock reject unknown served names with HTTP 400. Give different queries different results, including zero hits, malformed XML, missing links, timeouts, and article fetch failures. Keep existing tests able to opt into their simpler fixtures.
- [ ] Store the original 22 prompts, languages, and follow-up histories as test inputs. Include the electrical browser case separately. Record expected topic and explicitly forbidden distractor categories; do not encode a requirement that every question must return a library source.
- [ ] Add `test_catalog_name_is_not_search_identifier`: catalog discovery succeeds, but a search must use the content-link identifier. Add a second test asserting that an invalid library search is reported as a failure rather than a successful empty search.
- [ ] Run `python3 -B -m unittest tests.test_kiwix_contract -v`; confirm these integration regressions fail before the repair.

### Task 2: Repair archive identity and selection compatibility

**Modify:** `app/kiwix.py`, `tests/test_kiwix_contract.py`, `tests/test_library_filter.py`, `tests/test_archives.py`.

**Create:** `app/retrieval_types.py`.

- [ ] Parse served names from same-service HTML content links. Preserve logical names, UUIDs, source dates, and content URLs separately. Do not synthesize served names by concatenating guessed dates or flavours.
- [ ] Test percent-encoded names, optional URL prefixes, absolute same-service links, missing/foreign links, duplicate logical names with different versions, stale selections, and archive updates. Invalid identity must become an explicit capability failure, not an arbitrary URL fetch.
- [ ] Resolve existing logical-name selections to matching catalog entries; preserve `None = all` and `[] = none`. Refresh mappings on catalog change; keep request selection independent of shared server state.
- [ ] For older catalogs without HTML links, probe the advertised name once under the shared deadline and cache a validated identity. If it fails, report identity resolution failure. Do not silently fall back to unrestricted search across all books.
- [ ] Run `python3 -B -m unittest tests.test_kiwix_contract tests.test_library_filter tests.test_kiwix_links tests.test_archives -v`.
- [ ] Verify the ten installed libraries with a read-only diagnostic search. Require zero identity-related HTTP 400 responses; zero hits remain a valid outcome.

### Task 3: Make retrieval failures observable and bounded

**Modify:** `app/kiwix.py`, `app/engine.py`, `app/server.py`, `emergency.py`, `app/i18n.py`.

**Create:** `tests/test_retrieval_diagnostics.py`.

- [ ] Replace broad silent catches with classified outcomes: catalog unavailable, identity invalid, HTTP failure, timeout, parse failure, zero hits, fetch failure, unsupported format, no relevant passage, and budget omission. One failed library must not discard other libraries' successes.
- [ ] Report availability separately from search outcome: catalog reachable does not establish search health. Treat tags such as `_ftindex:no` as capability hints, not sufficient reason to disable a library; the diagnostic showed that some such archives still return results.
- [ ] Add a `retrieval` SSE event and additive final metadata. CLI output must expose the same summary. Keep detailed error bodies out of normal user messages; diagnostic output may include bounded status and sanitized paths.
- [ ] Introduce one request deadline shared by searches and fetches. Initial proposed defaults: 8 seconds, four in-flight HTTP requests, two query attempts per library, at most 20 search requests and 12 article fetches. Check the remaining deadline before scheduling work and cap individual socket timeouts to it. Executor shutdown must not wait indefinitely for pending work.
- [ ] When selections exceed the request allowance, schedule by query/source-language suitability with a first-attempt fairness rule before retries. Record every unsearched library as `not_searched_budget`; never report all selected libraries as searched. Test more than ten selected libraries and a relevant late catalog entry.
- [ ] Test one-library failure, all-library failure, disabled Kiwix, explicit empty selection, successful zero-hit search, cancellation, and slow responses. Assert distinct messages and useful surviving sources.
- [ ] Run `python3 -B -m unittest tests.test_retrieval_diagnostics tests.test_server_security -v`.

### Task 4: Construct useful multilingual and conversational queries

**Create:** `app/query_planner.py`, `config/retrieval-topics.json`, `tests/test_query_planner.py`.

**Modify:** `app/engine.py`, `app/retrieval_types.py`.

- [ ] Preserve whole words and meaningful phrases; do not send the existing six-character BM25 stems to Kiwix. Remove conversational framing and irrelevant numbers without losing age, concentration, timing, or negation from the preserved request scope.
- [ ] Build concise topic phrases from reviewed EN/PT/ES vocabulary and symptom combinations. Recognize concepts such as unresponsive plus gasping, choking infant, chemical water contamination, and allergy with airway symptoms. These are retrieval routes, not medical diagnoses or instructions.
- [ ] For each selected library language, create up to two lexical alternatives. Use explicit multilingual concept mappings; if a concept is unknown, retain normalized lexical queries and report limited cross-language coverage. Do not invent translations or force unrelated matches.
- [ ] Resolve follow-ups against recent user turns regardless of the old four-token cutoff. The current user statement overrides prior facts; topic changes reset inherited context. Assistant-generated diagnoses are not authoritative retrieval context.
- [ ] Add parameterized tests for the 22 inputs and held-out paraphrases. Required cases include EN/PT/ES gasping descriptions, an unconscious eight-month-old follow-up, the second injector follow-up, a topic change to a kitchen fire, and non-emergency queries about engines or camera repair.
- [ ] Run `python3 -B -m unittest tests.test_query_planner -v` and record planned queries alongside original prompts in diagnostic output.

### Task 5: Extract complete passages from long articles

**Create:** `app/passages.py`, `tests/test_passages.py`.

**Modify:** `app/kiwix.py`, `app/retrieval_types.py`.

- [ ] Replace the 20,000-character all-or-nothing return with structural extraction from bounded HTTP bodies. Proposed maximum HTML response is 8 MiB; enforce the limit while streaming, including when no content length is provided. An oversized response is reported explicitly.
- [ ] Preserve headings, paragraphs, lists, table headers and rows, warnings, units, and links to original sections. Remove navigation and scripts. A numbered procedure remains a complete block with associated cautions; do not cut off later steps to satisfy a character target.
- [ ] Produce heading-scoped candidate passages. Split long prose only at complete block boundaries; retain heading ancestry and adjacent scope/warning blocks. If a procedure is too large to fit safely, omit it with a reason and link to the full section.
- [ ] Test synthetic 100,000-character articles with relevant sections near the end, malformed HTML, duplicate boilerplate, headings with no anchor, tables of quantities, and procedures whose last step contains a warning. Confirm exact source text remains traceable.
- [ ] Cache extracted passages by archive UUID/version, canonical article URL, and extractor version. Bound disk and memory use; do not reuse content across updated archives.
- [ ] Run `python3 -B -m unittest tests.test_passages tests.test_kiwix_links -v`.

### Task 6: Select relevant evidence before applying final result limits

**Create:** `app/retrieval.py`, `tests/test_passage_ranking.py`.

**Modify:** `app/kiwix.py`, `app/knowledge.py`, `app/engine.py`.

- [ ] Fetch up to eight search candidates per queried library, deduplicate into a pool capped at 40, and choose article fetches within Task 3's shared budget. Preserve native rank and query provenance instead of relying only on raw title overlap.
- [ ] Score extracted passages using topic phrase coverage, BM25 relevance, heading evidence, age/context compatibility, and article type. A single shared word must not establish emergency relevance. Prefer directly applicable first-aid sections over background, equipment repair, or unrelated uses of the same word.
- [ ] Use age, negation, and subject scope to prevent pediatric/newborn/adult instructions being treated as interchangeable. An unspecified age must not silently become neonatal or pediatric. Exclude inapplicable passages; preserve material disagreements between applicable sources through the conflict policy rather than hiding one side.
- [ ] Refill from the candidate pool after extraction or relevance rejection, within the deadline. Apply final source limits after filtering, not before. Deduplicate overlapping passages from the same article and materially identical content across libraries.
- [ ] Add adversarial tests for `Seizure Salad`, two-stroke diesel engines, Infant Optics cameras, CO-detector teardown, and food-processor repair. Also test that those documents remain retrievable for actual repair or encyclopedia questions.
- [ ] Test archived sources retain dates and warnings; prefer equally relevant current evidence without pretending a recent encyclopedia snapshot makes every medical claim current.
- [ ] Run `python3 -B -m unittest tests.test_passage_ranking tests.test_relevance_gate tests.test_search_quality -v`.

### Task 7: Allocate context jointly and preserve accurate citations

**Modify:** `app/engine.py`, `app/retrieval.py`, `app/i18n.py`, `tests/test_retrieval.py`.

**Create:** `tests/test_context_selection.py`.

**Also create:** `app/source_policy.py`, `config/source-policy.json`, `tests/test_source_policy.py`, `tests/test_local_knowledge_preservation.py`.

- [ ] Rank guide and library passages in one candidate set. Remove the guide-first 7,000-character exclusion. Retain `context_chars` as a documented optional upper bound on total source text for compatibility, but apply it after joint selection; do not silently change an explicit local override.
- [ ] Use the existing backend token accounting to reserve system prompt, current question, useful history, output tokens, and context margin. Without a model, use a bounded extractive display allowance. Avoid counting a large hypothetical prompt repeatedly when a conservative preselection can reduce work.
- [ ] Reward complementary evidence and avoid redundant guide passages. Protect an applicable local procedure according to the preservation policy; replace lower-relevance local material where justified. Do not impose a quota that forces weak Kiwix passages into an answer. Reviewed supersession and unresolved conflicts take precedence over relevance-score tie breaking.
- [ ] Implement the conflict record and reviewed precedence policy above. Start with no invented authority rankings; add only explicitly reviewed source rules. Test local-correct/library-wrong, local-outdated/library-authoritatively-revised, unknown dates, conflicting quantities, different age/concentration scopes, repeated copies of one source, and an unresolved conflict under a tiny context allowance. Use synthetic procedures for mechanical tests; domain fixtures require independent review.
- [ ] Hash all local guide/personal-document fixtures before and after retrieval, indexing, cache cleanup, archive migration, and rollback tests. Require unchanged paths and bytes. Verify guide-only retrieval still works when every Kiwix request fails and that an applicable personal document remains discoverable with Kiwix enabled.
- [ ] Preserve complete procedures. Recompute inclusion after model fitting, and assign citation numbers only once final selection is stable. Keep excluded references available separately with an omission reason; they must not appear as evidence supplied to the model.
- [ ] Test small and large backend contexts, fallback token estimates, long history, no model, no relevant sources, all sources too large, and stable citation links. Verify excluded text is absent from the actual messages and included text is present exactly once.
- [ ] Run `python3 -B -m unittest tests.test_context_selection tests.test_source_policy tests.test_local_knowledge_preservation tests.test_retrieval tests.test_archives -v`.

### Task 8: Prepare PDF collections for offline retrieval

**Create:** `app/document_index.py`, `config/document-tools.json`, `tests/test_document_index.py`, `tests/test_document_tools.py`.

**Modify:** `app/prepare.py`, `app/startup.py`, `app/config.py`, `emergency.py`, `.gitignore`, `docs/downloads.md`.

- [ ] Add an explicit `index-libraries` CLI operation and an optional setup step for selected document collections. Indexing runs before an emergency query, has progress and cancellation, and never downloads tools or starts OCR during answer generation.
- [ ] Resolve document paths from the collection manifest. Parse the known `var DATABASE = [...]` data format with a narrowly validated data parser; never execute JavaScript or use unrestricted evaluation. Reject unknown expressions, foreign URLs, traversal, and paths escaping the selected archive. Use a bounded same-service fetch for each document.
- [ ] Package a pinned `pdftotext` executable through the existing verified-download workflow, with per-platform hashes and redistribution/license notices. Unsupported platforms or missing tooling receive a clear preparation state. Existing HTML retrieval remains functional. Document the exact supported matrix before enabling downloads.
- [ ] Extract native PDF text page by page in a subprocess with timeout, output-size, and process cleanup limits. Proposed initial limits are 256 MiB per PDF, 2,000 pages, and 120 seconds per document; report limit failures and permit explicit preparation-time overrides. Detect empty/scanned or poorly extracted pages instead of treating them as readable evidence.
- [ ] Preserve PDF title, archive version, page ranges, and original PDF links. Do not interpret garbled multi-column text or broken dose tables as a valid procedure. Exclude suspect blocks and expose coverage gaps. Scanned pages require a separate explicit OCR preparation step or remain browse-only; no silent claim of full PDF coverage.
- [ ] Store passages in a local SQLite FTS5 index under an ignored `indexes/` directory. Check FTS5 support in the shipped Python builds. Missing FTS5 yields an explicit unsupported-index state rather than runtime failure. Key entries by archive identity, document identity/hash, extraction version, and page range.
- [ ] Build a replacement index transactionally, then atomically activate it. Interrupted preparation retains the prior valid index. Archive replacement, deselection, or removal must not serve stale or unselected passages; reclaim superseded index data through an explicit cleanup operation.
- [ ] Test searchable synthetic PDFs, scanned PDFs, broken tables, malicious manifests, oversized downloads, extractor failure, cancellation, offline operation, and index migration. Query the prepared index using the same planner/ranking path as native HTML sources.
- [ ] Run `python3 -B -m unittest tests.test_document_index tests.test_document_tools -v`. Run an installed-extractor smoke test separately and report any skipped platform checks explicitly.

### Task 9: Surface capabilities and source usage in the browser and CLI

**Modify:** `web/app.js`, `web/style.css`, `app/i18n.py`, `app/server.py`, `emergency.py`.

**Create:** `tests/test_retrieval_ui.js`.

**Modify tests:** `tests/test_stream_completion.js`, `tests/test_library_filter.py`, `tests/test_server_security.py`.

- [ ] Distinguish selected, reachable, searchable, document-index-needed, partially indexed, temporarily failed, and browse-only states. Keep these labels concise and localize them in EN/PT/ES.
- [ ] After each answer, show whether library passages were actually supplied, whether searches failed, or whether no relevant passages were found. Do not present successful catalog discovery as successful evidence retrieval.
- [ ] Display included source section and date, with article anchor or PDF page link. Put omitted references behind a separate disclosure with a reason. Preserve the existing caution that source inclusion does not independently verify every generated claim.
- [ ] Display unresolved conflicts and reviewed corrections in both browser and CLI. Preserve their notices in extractive/no-model mode and interrupted responses. A source omitted for budget must not erase an already identified conflict notice.
- [ ] Keep library selection isolated per browser. Test saved logical selections across archive updates, deselection during a request, reconnection, no model, interrupted generation, and partial retrieval failure. The response must describe the selection captured when its request began.
- [ ] Add a CLI `diagnose-retrieval` operation that accepts a prompt/language and emits structured stage results without generating an answer. Default output must not persist private prompts; saving a diagnostic is explicit.
- [ ] Run `node tests/test_retrieval_ui.js`, `node tests/test_stream_completion.js`, and the focused Python server/selection tests. Verify the actual browser manually against one success, zero-hit, failure, and browse-only case.

### Task 10: Evaluate retrieval and answers against real libraries

**Create:** `tests/manual/retrieval_eval.py`, `tests/manual/retrieval_manifest.json`, `tests/manual/fixtures/`.

**Modify:** `tests/manual/README.md`, `docs/technical-reference.md`, `docs/troubleshooting.md`.

- [ ] Freeze the evaluation inputs before tuning: the 22 API cases, the electrical case, at least 24 held-out paraphrases/EN/PT/ES variants/follow-ups, and at least 12 negative or ambiguous cases. Include unrelated engineering queries so emergency routing does not override user intent.
- [ ] Inspect installed references to annotate gold-relevant sections, required context, and forbidden distractors. Mark absent coverage explicitly. Do not grade against hand-selected short queries; the evaluator must submit natural questions through the production planner and final prompt builder.
- [ ] Add `--manifest`, `--output`, and `--generate` evaluator options. Retrieval-only mode records actual queries, HTTP outcomes, candidate/filter counts, passage provenance, prompt inclusion, citations, elapsed time, and selected archive versions. Generation mode additionally saves answers and review labels.
- [ ] For the known original failure cases, require no invalid identifiers, no swallowed errors, no forbidden distractor in final context, and no selected-but-omitted passage falsely reported as included. At least one gold-relevant library passage must reach the prompt for every curated critical case whose installed source fits the available context.
- [ ] On the held-out supported cases, target at least 90% gold-passage recall in final context and at least 90% relevant included passages by human annotation. Report exact numerators and denominators, EN/PT/ES separately, plus unsupported-case abstention. These are proposed release gates, not current achieved results or medical safety certification.
- [ ] Test cold and warm caches, native-search-only, PDF-index-enabled, one selected library, all selected libraries, unavailable Kiwix, model unavailable, and outbound internet blocked. Targets on the user's machine: warm retrieval p95 at most 5 seconds; cold retrieval completes or reports degradation within the configured 8-second deadline plus at most one second cleanup tolerance.
- [ ] Repeat critical answer-generation cases three times using the existing Qwen configuration. Review correct immediate actions, harmful additions, age/scope errors, and whether citations support the attached claims. Compare to the saved baseline. A serious new safety error blocks rollout; a clinician/first-aid reviewer must approve claims of emergency reliability.
- [ ] Run `python3 -B -m unittest discover -s tests`, then `python3 tests/manual/retrieval_eval.py --manifest tests/manual/retrieval_manifest.json --output /tmp/emergency-retrieval-eval.json`. Run generation only after retrieval gates pass.

### Task 11: Roll out with migration and rollback checks

**Modify:** `docs/technical-reference.md`, `docs/troubleshooting.md`, `docs/downloads.md`, `config/settings.json`.

- [ ] Deliver separately reviewable changes: identity/diagnostics; HTML retrieval and context selection; PDF preparation; UI and evaluation completion. Do not label the identity-only delivery a comprehensive fix.
- [ ] Version cached catalogs, extracted passages, and document indexes. Document new settings and defaults, the treatment of existing `context_chars`, required preparation, disk usage, supported extraction platforms, and source-language behavior.
- [ ] Validate the new build on an isolated server with the same installed libraries and model settings. Avoid concurrent model generation that interferes with the user's running instance; retrieval-only checks do not require the model.
- [ ] At the authorized rollout step, restart the application with the new code, refresh library identities, preserve browser selection semantics, and prepare selected document indexes. Run the live smoke suite again; do not rely solely on an in-process patched diagnostic.
- [ ] Verify rollback: prior code can still read unchanged configuration, generated indexes can be ignored or rebuilt, and browsing/guide-only operation remains usable. Do not delete the user's archives or overwrite local settings to roll back.
- [ ] Publish the evaluation summary with archive versions, unsupported collections/pages, platform gaps, and answer-review outcomes. Completion requires the release gates below, not merely passing unit tests.

## Release gates

- Every selected installed library resolves to a valid identity or an explicit actionable failure.
- No all-library search failure is displayed as a successful empty search.
- Real natural-language questions reach the source selection stage; there is no dependency on manually rewritten diagnostic queries.
- Relevant sections of long articles are retrievable without clipping procedures or erasing warnings.
- High-relevance library passages compete fairly with guides for available model context.
- Local guide and personal-document files remain byte-for-byte unchanged; applicable local evidence is not displaced solely by the volume of library matches.
- Material known conflicts are resolved only through scoped reviewed precedence or visibly reported as unresolved, including under context pressure and without an LLM. No averaging or silent synthesis of incompatible procedures is allowed.
- Known incidental-match distractors never enter final context for the emergency cases.
- Selected PDF collections have verified text coverage or explicit per-document/page limitations; installed does not mean indexed.
- Follow-ups and EN/PT/ES variants meet the same scoped retrieval expectations where source coverage exists.
- Source provenance, dates, inclusion flags, and citation numbers agree with the actual model input.
- Offline operation, per-browser selection, time/resource limits, failure fallback, cache invalidation, and rollback are exercised.
- Retrieval evaluation meets the stated gates and answer review finds no serious new safety regression.

## Risks and deliberate limits

Better retrieval can expose outdated or unsafe source material more efficiently. Preserve source dates and scope, prefer applicable current evidence, and review generated advice; do not equate more citations with safer answers.

Deterministic query planning will have vocabulary gaps. Measure those on held-out questions and expand reviewed retrieval vocabulary when justified. Do not overfit the original 22 prompts or relax relevance until every prompt has a citation.

PDF extraction introduces packaging and layout risks. Keep preparation separate from serving, validate each supported platform, and report incomplete coverage. OCR support and source medical accuracy remain explicit limitations until independently validated.

## Plan review checklist

- [x] Identity, error visibility, query formation, passage extraction, ranking, context allocation, PDF ingestion, UI reporting, evaluation, and rollout each have an owner and tests in this plan.
- [x] The design preserves current selection semantics and offline/no-pip serving behavior.
- [x] Cold/warm caches, archive updates, source-language gaps, missing extractors, and failed preparation have explicit planned outcomes.
- [x] Success measures assess relevance and prompt inclusion, not simply the number of library links.
- [ ] Implementation is reviewed against these contracts before changing the running service.
