# Answer-quality follow-up: implementation and repeated evaluation

**Useful answers improved substantially, but the whole-suite quality gate has not passed.** The last full 96-answer comparison improved usefulness from 37 to 83 answers rated at least 3/4. Later targeted corrections passed 18 affected-case repeats and six burn repeats on their respective revisions. Failed development runs remain in the record. These selected passes do not establish a full-suite pass for the final code.

The implementation adds 22 versioned source-backed guidance units in English, Portuguese and Spanish, deterministic fallback help after rejected or unavailable generation, bounded action-condition and citation-support checks, and targeted eval selection through `--case`. Original rejected drafts remain undisplayed. Source conflicts do not grant the catalog automatic precedence. Overall claim support remains explicitly unverified outside recognized patterns.

## Full repeated comparison

Each revision ran the same 32 cases for three trials. All captures received bound reviews of usefulness, unsafe instructions, citation support and withholding.

| Measure | Baseline `aff2ec4` | Initial `0d2e1fa` | Refined `ecf0d23` |
| --- | ---: | ---: | ---: |
| Reviewed answers | 96/96 | 96/96 | 96/96 |
| Generated answers | 55 | 12 | 21 |
| Source-backed fallbacks | 0 | 41 | 65 |
| Notices | 41 | 43 | 10 |
| Usefulness at least 3/4 | 37 | 35 | 83 |
| Major unsafe findings | 17 | 4 | 3 |
| Major citation findings | 28 | 4 | 4 |
| Unnecessary withholding identified | 0 | 6 | 0 |
| Withholding assessment uncertain | 38 | 34 | 7 |
| Invalid numeric citations | 0 | 0 | 0 |
| Failed/incomplete displayed captures | 0 | 0 | 0 |
| Quality screen | Fail | Fail | Fail |

Counts overlap and are not a combined score. Most substantive refined responses were source-backed fallbacks. Free-form generation still introduced unsafe or unsupported instructions. Zero invalid citation IDs did not establish semantic support.

There are **90 exact-request pairs** between baseline and refined runs. Six live follow-ups differ because their preceding answers differ. On exact pairs, useful answers increased from 34/90 to 77/90, major unsafe findings fell from 17/90 to 3/90, and major citation findings from 27/90 to 4/90. Whole-run figures retain all conversations. See the [paired comparison](../../tests/evals/emergency_advice/baselines/repeated-2026-11-26/refined-full-comparison.md).

Median total response time was 16.31 seconds for baseline, 14.13 for initial candidate and 12.93 for refined; nearest-rank p95 was 31.93, 30.02 and 21.37 seconds. These are complete-request timings under uncontrolled load. First tokens can be disclaimers, so they do not measure time to useful advice or establish a causal speedup.

## Subsequent corrections and separate results

| Frozen revision / run | Captures | Useful ≥3 | Major unsafe / citation | Screen |
| --- | ---: | ---: | ---: | --- |
| `1bffd0a`, six affected cases × three trials | 18 | 18 | 0 / 0 | Selected-set pass |
| `1bffd0a`, separate development suite | 12 | 9 | 2 / 2 | Fail |
| `dd0af0f`, three routing cases × three trials | 9 | 8 | 1 / 1 | Fail |
| `dd0af0f`, full development rerun | 12 | 11 | 1 / 1 | Fail |
| `0d458d5`, two burn cases × three trials | 6 | 6 | 0 / 0 | Selected-set pass |

The 18-case repeat tested embedded-object removal exceptions, generator shutdown/re-entry, and stopping CPR at mere arrival of help or an AED. All 18 requests match their refined-run counterparts: usefulness increased from 15/18 to 18/18, and major unsafe/citation findings from 3/3 to 0/0. The repeat retained five minor safety and three minor citation findings. See its [bound review summary](../../tests/evals/emergency_advice/baselines/repeated-2026-11-26/final-affected-review-summary.md).

The development suite then exposed natural-language routing misses for cooking oil burning in a pan, low glucose with unsafe swallowing, and Spanish “me quemé.” Correcting the vocabulary supplied appropriate evidence and fallback. Relevant evidence alone did not prevent Spanish burn answers from weakening the stuck-clothing exception or reversing jewelry-removal timing. Those two exact failures became regressions. After the final burn correction, all six burn repeats produced complete source-backed fallbacks rated 4/4 with no identified safety or citation defects. See the [final burn review](../../tests/evals/emergency_advice/baselines/repeated-2026-11-26/burn-final-review-summary.md).

**345 captures across eight runs are preserved and reviewed.** None were retried in place, overwritten or excluded for failing. The 12 development cases informed implementation and are not an independent holdout. No new complete 96-answer run or complete 12-case run was performed on `0d458d5`; the final six-case pass does not replace earlier failed screens.

## What remains open

- General claim entailment and condition understanding remain unverified. A replay of the refined snakebite self-travel answer still passes the final bounded validator even though its travel advice is unsupported by the cited passage.
- Some known wording and conditions remain outside coverage, including blanket CPR movement restrictions. Some emergencies still receive notices when no eligible fallback is available.
- Conservative checks can withhold legitimate paraphrases, including generator maintenance/shutdown advice outside the supported emergency procedure. These limitations are documented in the [guard review](2026-11-26-final-action-guards.md).
- Independent clinical and native-language adjudication, new holdout cases, and a new complete release screen remain necessary before any clinical-approval claim. This work does not provide that approval.
- Native Windows/macOS execution of this revision awaits CI. Linux tests are not native-platform verification. Broader annotated retrieval precision and cold/warm/offline operating-matrix work remain outside this follow-up.

## Review method and provenance

Reviews are identified agent assessments, with an independent spot audit and engineering specification/quality review. Review bindings cover exact answer, request, supplied passages, terminal metadata, rubric and full reference manifest. Primary references were checked; the original local guides are not the clinical gold standard. This is not clinician certification.

An independent audit downgraded the initial burn fallback from usefulness 3 to 2: it omitted required loose covering, warmth and the explicit ice question. The same criterion was applied to later answers. A false CO density explanation was rated minor when the complete answer retained correct evacuation, emergency help and no-reentry actions; unsupported hazardous action exceptions were rated major. Detailed rationales remain in the bound reviews.

Withholding concerns displayed help. A `none` rating for a useful fallback does not certify rejection of the hidden draft; that draft remains unknown. Missing help lowers usefulness, and clear supplied evidence of omitted safe help can separately establish unnecessary withholding. No reduction in displayed unsafe instructions is counted as proof of prevented harm.

Runs were sequential on isolated loopback app instances, reusing Qwen_Qwen3.5-9B-Q4_K_M.gguf through llama.cpp b12719 CUDA and Kiwix 3.8.2 with ten archives. Context was 8192, temperature 0.2 and maximum output 2048 tokens. All runs share settings SHA-256 `a71063ea6fda3ee86989b5468d41c4e1c505938eef721ebe9bd7217bf688a669`. Launched roots, commits, file hashes, process identities and archive identities accompany the captures. An operator-supplied installation root alone does not attest app identity. Sampling, execution order and load remain uncontrolled; these results do not establish a causal improvement estimate.

The installed application, model and archive services were not restarted or modified. All 46 original knowledge-file paths and hashes remain unchanged. Only the isolated evaluation app servers were started and later stopped.

## Engineering verification and artifacts

Final full Python verification: **740 tests run, 20 skipped, no failures**. JavaScript fallback/source-order tests and syntax checks passed. Independent reviewers rechecked each correction. Process-local mutations removing guards caused captured-failure tests to fail and were restored. ZIP and tar exports include production guidance and exclude all tests/evals. The final evidence-only commit does not change the tested production code at `0d458d5`.

The [evidence index](../../tests/evals/emergency_advice/baselines/repeated-2026-11-26/README.md) links every portable capture, bound review, report and provenance record. [Verification summary](../../tests/evals/emergency_advice/baselines/repeated-2026-11-26/verification-summary.json) independently validates all 345 review bindings and run denominators. Raw SSE captures remain under the recorded `/tmp/advice-quality-*` directories; Git retains exact displayed answers, supplied passages, review evidence and raw-file hashes.

See the [eval instructions](../../tests/evals/emergency_advice/README.md) for new runs, targeted repeats, review templates, report generation and exact-request comparisons. Eval assets remain in Git and are excluded from installation downloads.
