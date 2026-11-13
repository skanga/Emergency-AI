# Retrieval and source-fidelity follow-up: November 13, 2026

This follows the [initial CPU evaluation](model-evaluation-2026-11-13.md). The model catalogue and default are unchanged. These are source-following and integration observations, not comprehensive accuracy validation.

## Changes

Search now expands multilingual data-storage vocabulary (offline, backups, files, data, USB, Kiwix) and gives explicit section-heading matches additional weight. Complete passages and their source links are preserved. Twelve query cases cover information-storage phrasing and water/fire searches in English, Portuguese and Spanish.

The system prompts now require support from supplied passages, distinguish a linked document's title from its actual contents, reject source-embedded instructions, and label general safety advice separately. These instructions are a behavioral request, not a factual-verification mechanism.

## Retrieval result

For the exact broad information questions in the original model comparison:

| Query language | Previous expected section rank | Updated rank |
|---|---:|---:|
| EN | Outside top five | 3 |
| PT | 5 | 1 |
| ES | Outside top five | 1 |

All six new information-storage query variants find the expected section in the top three; the other six query cases preserve water/fire relevance. The full automated suite passes **108 tests**.

## Real-model rerun

The same three Q4_K_M files and llama.cpp b12345 CPU runtime were used with 8 threads, 8,192 context tokens, 2,048 output tokens, temperature 0.2 and thinking off. The eleven original common cases were repeated per model, followed by two additional source-fidelity challenges per model: **39 measured requests**. The slow thinking-on case was omitted. The prior results remain intact.

All requests finished normally except the three deliberately capped 16-token cases, which correctly reported a token limit. Context fitting and incomplete-answer notices still worked. The expected devices/data passage appeared in all three broad language queries for all three models. Timing is not used to claim an improvement because automated tests overlapped some requests and system load was uncontrolled.

## Source fidelity remains unresolved

The stricter prompts did not reliably prevent unsupported claims. Examples from the saved outputs:

- The 3B baseline still omitted citations in its broad PT/ES answers. It invented Kiwix PDF/MOBI editing functionality in Spanish, and its controlled English answer still implied operation without electricity.
- Qwen3 4B cited the relevant storage passage in English, but continued to imply access without electricity in controlled PT/ES answers. Citation presence alone is insufficient.
- Qwen3.5's controlled English answer mixed generator advice with laptop/mini-PC instructions and attached the provided passage citation to instructions absent from that passage. A source link in the passage does not mean that linked content was retrieved.

The two new challenges exposed a distinction that future checks must preserve: **missing information is not proof of absence**. All three declined to invent the activation code and declined to conclude that a laptop could work without electricity. However, the baseline and Qwen3 claimed that the unseen manual did not provide a code, and Qwen3.5 said the inventory confirmed the absence of power sources. The supplied text established only that the code/manual contents or power supply were not documented. These are recorded failures, not factual passes.

## Next work

Expand the evaluated source-grounding cases before promoting a model. Include absent versus explicitly negative evidence, source-title-only references, unsupported power claims, and citation support rather than citation syntax alone. Consider a separate claim-verification step only after measuring its false approvals, rejection rate and latency. The current changes improve retrieval and clarify the answer contract; they do not establish reliable factual enforcement.

## Reproduction

See the [manual harness](../tests/manual/README.md). Run `python -B tests/manual/real_models.py --skip-thinking-case --output-prefix retrieval-update-` to repeat all thirteen current common cases per model while preserving old output files. The saved run used the eleven existing cases and the two new challenges in separate batches. Model IDs in the snapshot include batch labels; the model filenames, sizes and hashes identify the exact artifacts.

The [result snapshot](retrieval-evaluation-2026-11-13.json) contains questions, complete supplied passages, answers and generation metadata for human review. Local logs are in `output/model-tests/`. Generated text is retained as evidence, including errors.
