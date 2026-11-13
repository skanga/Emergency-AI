# Real-model evaluation: November 13, 2026

These are integration and source-following smoke tests, not medical validation or a comprehensive model benchmark. Generated answers are test artifacts, not emergency instructions. The model catalogue and default remain unchanged.

## Environment and method

- Windows; Intel Core Ultra 9 285H, 16 logical processors, approximately 64 GB installed RAM.
- NVIDIA RTX PRO 2000 Blackwell Laptop GPU (8 GB) was present but **not used**.
- Latest compatible portable llama.cpp CPU release at download: **b12345**, commit **2a4daf0e0**, reporting version 0.9.0-dev. Eight generation/batch threads, one slot, no GPU offload, seed 42.
- Q4_K_M models; 8,192-token context, temperature 0.2, 2,048-token output allowance and 256-token context margin. Thinking off except the named thinking-on case.
- All model files verified against their recorded sizes and SHA-256 hashes. Candidate URLs are pinned to Hugging Face revisions in the [manifest](../tests/manual/model_manifest.json).
- Final comparison ran after downloads completed. One warm-up per model preceded the measured requests. Models ran sequentially; OS caches and normal prompt-cache reuse remained enabled. No thermal or battery controls were applied.
- Eleven common cases: fictional inventory arithmetic, missing facts, a source-embedded instruction, broad guide retrieval in English/Portuguese/Spanish, deliberate output truncation, oversized history, and a controlled relevant guide section in each language. Qwen3.5 also received a thinking-on case.
- Broad retrieval uses the existing knowledge search. Controlled retrieval supplies the complete **Devices and data** section of the energy guide directly, separating retrieval quality from generation behavior.

## Results

| Model (Q4_K_M) | Median guide answer | Median first visible text | Peak server working set | Guide answers with citations |
|---|---:|---:|---:|---:|
| Qwen2.5 3B Instruct | 10.4 s | 4.1 s | 3.67 GiB | 4/6 |
| Qwen3 4B Instruct 2507 | 14.2 s | 6.0 s | 6.07 GiB | 6/6 |
| Qwen3.5 4B | 15.5 s | 6.0 s | 5.71 GiB | 6/6 |

Latency and first-visible-text numbers are medians of the six guide cases per model, excluding the deliberately limited, context-pressure and thinking-on cases. Peak working set covers the server process over its run, including mapped model weights and buffers. It is not the minimum total system RAM required. These single-run numbers should not be treated as precise speed rankings.

## What the real requests established

- All three models loaded and answered through the application's actual llama.cpp client and answer engine.
- All three correctly added the fictional 17 and 6 packs, acknowledged that the fictional activation code was absent, and ignored the one tested source-embedded instruction. This small sample does not establish general prompt-injection resistance.
- All three reported a `length` finish when capped at 16 output tokens. The app displayed its incomplete-answer notice.
- All three dropped the oversized old conversation, retained the current question and complete relevant source, and answered within the configured context budget. The real llama.cpp tokenizer and reported server context were used.
- Normal thinking-off cases produced no reported reasoning. No raw thinking trace was included in the saved visible answers.

## Quality findings

The newer models cited sources in all six guide answers, versus four of six for the 3B baseline. The baseline's uncited answers were the broad Portuguese and Spanish queries; supplying the relevant section directly restored citations. **Citation presence is not a factual-accuracy score.**

The broad English offline-information query retrieved food-consumption and general checklist passages, but missed the directly relevant Devices and data section. The Spanish query also missed that section. The same retrieval results were used across models for each language. Retrieval quality needs its own evaluation and improvement.

Specific observed problems:

- **Qwen2.5 3B:** the broad English answer added a waterproof/fireproof storage-container recommendation absent from its supplied passages. Its controlled English answer implied the digital setup could work without an external power source, without establishing a battery or other power supply.
- **Qwen3 4B Instruct:** citation coverage improved, but controlled Portuguese/Spanish answers still overstated operation without electricity. A broad English claim about storing USB files cited a checklist introduction that did not contain that detail.
- **Qwen3.5 4B:** the broad English answer incorrectly described the AI as browsing the kit interface. Its controlled English answer added generator instructions not present in the supplied passage and attached the same passage citation. That passage contains a generator-safety source link, but the linked document was not supplied to the model, so the generated instructions were not verified from the retrieved context.

The energy guide itself contains device power-consumption estimates. Repeating those estimates accurately is not evidence that the estimates are valid across hardware; content review remains a separate task.

## Interpretation and next steps

Both 4B candidates are technically usable through the updated client. Qwen3-4B-Instruct-2507 remains a reasonable first additional option because its generation mode is simpler; this test does not establish it as more accurate overall. Qwen3.5 is also viable, subject to the thinking-mode result below and broader evaluation. Neither deserves an automatic default switch based only on this small sample.

Before choosing a new default, expand the source-grounding set, measure unsupported claims and citation support, improve retrieval for offline-information queries, and test lower-memory computers. GPU acceleration, Ollama, medical accuracy, long answers, battery consumption, and statistical repeatability were not tested here.

## Thinking-mode follow-up

With thinking off, Qwen3.5 answered the fictional inventory question correctly in **5.98 seconds**, showing its first answer text after **2.98 seconds**. With thinking on at the same temperature (0.2), it still answered correctly and finished normally, but took **139.22 seconds**, with no visible answer text until **135.55 seconds**. The client correctly detected reasoning and kept it out of the visible answer. The 2,048-token total generation allowance was sufficient for this run.

The publisher recommends different sampling settings for thinking, including a higher temperature. Our common comparison intentionally used the current app settings, not model-specific optimum settings. A separate follow-up changes only temperature to 1.0; other sampling parameters remain at server defaults. This is not a full implementation of the publisher's sampling recipe. [Qwen3.5 model card](https://huggingface.co/Qwen/Qwen3.5-4B).

The temperature-1.0 follow-up reached the 2,048-token limit while reasoning, without a final answer. The app correctly showed the limit warning and source passages. That process survived a tool-server restart, while a recovery attempt collided with it during warm-up; its timing and memory are excluded from the comparison. This outcome is not evidence that higher temperature is generally worse, or that a larger budget would fix the behavior.

The fallback revealed a presentation bug: it said no model was running even though the model had reasoned without completing an answer, and the warning lacked a paragraph break before the passages. Both are fixed in EN/PT/ES. A clean real-model rerun with thinking enabled and a 16-token limit reproduced the fallback in **3.47 seconds** and verified the corrected wording and separation. The regression suite remains at **106 passing tests**.

Keep thinking off by default for this workload. The thinking-on sample did not improve the already-correct arithmetic answer; this says nothing about its benefit on harder questions.

## Reproduction and artifacts

Use the [manual harness instructions](../tests/manual/README.md). The harness is outside automatic CI and downloads nothing during its test run. Full local outputs and server logs are in `output/model-tests/`. The [portable result snapshot](model-evaluation-2026-11-13.json) contains 36 measured requests: the 34-request main matrix, the temperature follow-up, and the post-fix 16-token verification. Absolute workspace paths are replaced by `${REPO}`. The snapshot preserves pre-fix outputs as evidence rather than rewriting history.

Model sources: [baseline GGUF](https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF), [Qwen3-4B-Instruct GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF), [Qwen3.5-4B GGUF](https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF). Runtime: [llama.cpp b12345](https://github.com/ggml-org/llama.cpp/releases/tag/b12345).
