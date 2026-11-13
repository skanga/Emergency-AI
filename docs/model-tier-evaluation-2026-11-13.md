# Model recommendations by size: November 13, 2026

## Selected catalogue

| Tier | Catalogue ID | Choice | Recommended system RAM |
|---|---|---|---:|
| Lightweight | `lfm3-1.7b` | Official LFM3 1.7B Q4_K_M | 8 GB |
| Balanced / new default | `gemma4-e2b` | Unsloth Gemma 4 E2B Instruct UD-Q4_K_XL | 16 GB |
| Larger | `qwen35-9b` | Qwen3.5 9B Q4_K_M | 24 GB |
| Advanced high-memory option | `qwen38-27b` | Official Qwen3.8 27B, Unsloth UD-Q4_K_XL | 32 GB |

These are recommended starting points among the files tested for this application. They are not universal benchmark winners, validated minimum RAM requirements, or evidence of medical accuracy. The default changes for new setup; existing saved IDs keep their original files. `light`, `standard`, `strong` and `llama3b` remain available as legacy choices. No GGUF weights are committed.

LFM3 uses the LFM Open License v1.0; read its terms. Gemma 4 and the Qwen/Ministral alternatives use Apache 2.0. `qwen35-2b` is the lightweight Apache alternative. `qwen3-4b` and `ministral3-8b` remain alternatives. The old Qwen2.5 3B `standard` ID retains its original Qwen Research License.

## Test method

We evaluated **15 GGUF files with eight cases each (120 measured requests)**, including paired quantizations. The files represent fewer than 15 underlying model families. All public downloads were verified by expected size and SHA-256 and pinned to Hugging Face revisions. The two user-provided files were read and hashed in place, without copying, modifying, or adding them to Git. Decision/classification models were excluded as requested.

Hardware: Windows, Intel Core Ultra 9 285H, 64 GB installed RAM. The NVIDIA GPU was not used. Runtime: latest compatible portable llama.cpp CPU release at preparation, b12345 / commit 2a4daf0e0. Parameters: 8 generation/batch threads, one server slot, 8,192-token context, seed 42, and **512 output tokens** for questions requesting concise answers. The application's normal output default remains 2,048 tokens. Long-context and low-RAM hardware behavior were not measured.

Cases: fictional inventory arithmetic, absent activation code, source-embedded instruction, unseen linked manual, missing electricity evidence, and the complete Devices and data guide section in EN/PT/ES. Sources were controlled to isolate generation from the retrieval issues documented separately. All models received the same cases, but model-specific samplers differed. This is an application-fit comparison, not an isolation experiment for quantization quality or model architecture.

After generic temperature-0.2 settings caused repetition in Qwen3.5 2B, the final runs used publisher sampler profiles: Qwen3.5/Qwen3.8 non-thinking temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5, repeat_penalty 1; Gemma 4 temperature 1, top_p 0.95, top_k 64; Ministral temperature 0.05; LFM3 temperature 0.1, top_k 50, repeat_penalty 1.1; local LFM2.5 temperature 0.1, top_k 50, repeat_penalty 1.05. Legacy baselines and Qwen3-4B used the app's temperature-0.2 configuration. Thinking was requested off for every file. The local distill used the Qwen non-thinking profile provisionally; that is not a verified publisher recipe for this exact distill.

## Measurements

| File / model variant | Download / file GB | Median guide answer | Peak server GiB | Normal finishes |
|---|---:|---:|---:|---:|
| light | 0.99 | 11.2 s | 1.90 | 7/8 |
| qwen35-2b | 1.40 | 5.2 s | 2.19 | 8/8 |
| unsloth-qwen35-2b | 1.34 | 3.8 s | 1.99 | 8/8 |
| lfm3-1.7b | 1.10 | 6.0 s | 1.95 | 8/8 |
| standard | 1.93 | 8.4 s | 3.51 | 8/8 |
| qwen3-4b | 2.50 | 16.3 s | 5.42 | 8/8 |
| qwen35-4b | 3.01 | 14.0 s | 4.98 | 8/8 |
| gemma4-e2b | 3.46 | 6.2 s | 2.44 | 8/8 |
| unsloth-gemma-4-e2b-it | 3.18 | 4.7 s | 2.44 | 8/8 |
| strong | 4.68 | 18.0 s | 7.70 | 8/8 |
| ministral3-8b | 5.20 | 25.0 s | 9.38 | 8/8 |
| qwen35-9b | 6.17 | 27.1 s | 8.57 | 8/8 |
| local-lfm25-24b-a2b | 14.53 | 26.4 s | 24.43 | 5/8 |
| unsloth-qwen38-27b | 17.66 | 60.3 s | 19.58 | 8/8 |
| local-qwen38-distill-35b | 21.71 | 12.7 s | 34.98 | 8/8 |

Guide latency is the median of three language cases. Timings are illustrative: models ran sequentially, but some downloads and development checks overlapped, and caches, thermals and OS scheduling were uncontrolled. Peak Windows process working set is not minimum system RAM and excludes other processes. Recommended RAM adds headroom; tests did not validate those recommendations on smaller machines. Normal finishes measure backend completion, not factual correctness. A token-limit stop displayed the incomplete-answer notice and, when no answer text existed, source passages.

## Why these choices

- **LFM3 1.7B:** completed all eight cases, got the arithmetic right, cited the supplied source IDs, and avoided the old 1.5B model's repeated Spanish output. Its approximately 1.1 GB file and measured footprint suit the lightweight tier. Some general advice and power-availability ambiguity remained; it is not a factual verifier. Its custom license is a tradeoff, so an Apache alternative remains available.
- **Unsloth Gemma 4 E2B:** both tested Gemma files completed cleanly, answered the missing-evidence cases directly, and kept the three guide answers close to supplied text. The Unsloth file is smaller (3.18 GB versus 3.46 GB), with no observed regression on this set, so it is the balanced/default download. E2B describes effective computation; the complete weights are larger than 2B.
- **Qwen3.5 9B:** a more suitable current larger option than Qwen2.5 7B in this sample, with consistent citations and fewer obvious language/citation failures. It had a smaller measured footprint than Ministral 3 8B. Additional general advice and overstatements about missing information remained. This small set does not establish that it is more accurate than Gemma on harder tasks.
- **Official Qwen3.8 27B:** successfully runs with the current client and Unsloth quantization, but is substantially slower on this CPU and requires a much larger download. It is an advanced option, not a replacement for the portable default. More parameters did not justify a blanket recommendation for ordinary kit questions.

## Quantization and local-file observations

Unsloth's label alone is not evidence of better factual quality. The paired Gemma result supports choosing its smaller download, but one seed and eight questions cannot prove quantizer superiority. Unsloth Qwen3.5 2B still introduced unsupported details, including confused advice about bags near plugs and calling a Raspberry Pi a laptop processor. The flat Q4_K_M variant also fabricated source IDs and unsupported details. Both need the same source-fidelity caution; neither displaced LFM3 in the lightweight recommendation.

The original `light` Qwen2.5 1.5B answered 17 + 6 as **21** and ran into the output cap in Spanish. The older `strong` 7B produced an invalid citation and mixed Chinese into a Spanish answer. They are retained for compatibility, not presented as current recommendations.

The user's **LFM2.5-24B-A2B** file produced reasoning despite the off request and exhausted the 512-token budget before a visible answer in all three guide cases. The app fell back to passages correctly. This is an observation about this exact local GGUF and setup, not every LFM2.5 build; it is not a good fast-answer default for the current configuration.

The user's **Qwen3.8-35B-A3B-Distill.i1-Q4_K_M** completed the cases and was much faster than the dense official 27B on this CPU, but used about 35 GiB peak server working set. Its metadata identifies **Qwen3.6-35B-A3B as the base**. It is a third-party distill file, not the official Qwen3.8 checkpoint. Some guide answers attached citations to generator advice absent from the supplied excerpt. No public download was inferred from the local filename; it is documented as a local high-memory experiment rather than a catalogue entry.

## Shipped behavior and compatibility

The catalogue now supplies sampler presets for its exact llama.cpp filenames. Precedence is global defaults, catalogue sampler preset, explicit backend override, then explicit exact-model override. Presets do not override the user's thinking request. Generic compatible APIs receive only supported standard sampler fields; llama.cpp and Ollama also support top_k, min_p and repeat_penalty. Invalid sampler values fail validation.

The menu and README identify current recommendations, alternatives, RAM estimates and licenses. Legacy IDs never change artifact identity; saved setup and resume retain their original meaning. New setup uses Gemma 4 E2B. Model files are revision/hash pinned; runtime preparation still checks for the newest compatible llama.cpp build.

## Reproduction and limits

See [manual test instructions](../tests/manual/README.md), the three pinned public manifests, and the [full result snapshot](model-tier-evaluation-2026-11-13.json). Local file paths are replaced with `${LOCAL_MODEL_DIR}` and workspace paths with `${REPO}`. Model names, quantizations, hashes, settings, questions, supplied passages, visible answers and generation metadata are retained. No hidden reasoning traces or weights are stored in the snapshot.

Source fidelity is still unresolved across the catalogue. Citation syntax is not a support check; missing evidence is not evidence of absence. The bundled power-consumption estimates were only checked for faithful repetition, not independently validated. Medical guidance, complex tasks, battery use, full-context memory, GPU acceleration, other operating systems and statistical repeatability were not evaluated here. The recommendations can change with broader testing, but a published model ID must not be silently remapped to new weights.

Publisher sources: [LFM3](https://huggingface.co/LiquidAI/LFM3-1.7B), [Gemma 4 E2B](https://huggingface.co/google/gemma-4-E2B-it), [Qwen3.5 9B](https://huggingface.co/Qwen/Qwen3.5-9B), [Ministral 3 8B](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512), [Qwen3.8 27B](https://huggingface.co/Qwen/Qwen3.8-27B), [local LFM family](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B), [Unsloth Gemma quantization](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF), [Unsloth Qwen3.5 quantization](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF), [Unsloth Qwen3.8 quantization](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF).

## Verification

All 115 automated tests pass, along with JavaScript syntax and diff whitespace checks. One earlier full run encountered a transient Windows socket abort in the unchanged origin-rejection test; the isolated security suite and subsequent full runs passed. Legacy filenames, URLs, byte sizes and SHA-256 hashes were compared with the prior catalogue and are unchanged. No GGUF files are tracked by Git.
