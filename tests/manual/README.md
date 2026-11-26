# Real-model smoke comparison

This manual check loads real GGUFs. It is not part of CI, and its answers are unvalidated model output, not emergency instructions. It checks local integration and a small set of source-following behaviors; it does not establish medical accuracy or broad model quality.

The manifest records the three tested Q4_K_M files and their SHA-256 checksums. The two candidate downloads are pinned to Hugging Face revisions. Downloads total about 7.44 GB (6.93 GiB); allow additional space and RAM for the runtime and inference.

From the repository root, install the latest portable CPU runtime and download the files using the existing integrity-checked downloader:

```python
import json
from pathlib import Path
from app.prepare import T, download, get_llama
from app.config import platform_key

assert get_llama(platform_key(), T["en"])
for model in json.loads(Path("tests/manual/model_manifest.json").read_text(encoding="utf-8")):
    download(model["url"], str(Path("models") / model["file"]),
             expected_size=model["size_bytes"], sha256=model["sha256"])
```

Then run:

```text
python -B tests/manual/real_models.py
```

For the isolated Qwen3.5 thinking follow-up at temperature 1.0, run `python -B tests/manual/real_models.py --thinking-temperature 1.0`. This writes a separate result file. Other sampling parameters stay at server defaults. To reproduce the quick reasoning-only fallback check, use `--thinking-temperature 0.2 --thinking-max-tokens 16`.

Optional positional arguments restrict the run to manifest IDs, for example `standard`. The script verifies model hashes, starts one server at a time on loopback port 18931, and stops each server in a `finally` block. Ensure this port is free before running. It does not change the model catalogue, local settings, or saved setup choices. On Windows it records the server process peak working set; other platforms omit that measurement.

Parameters: CPU only, 8 generation and batch threads, one server slot, seed 42, 8,192 context tokens, temperature 0.2, default 2,048 output tokens, thinking off except the explicit Qwen3.5 thinking-on case. No ZIM downloads or GPU runtime are required.

The thirteen common cases cover fictional inventory arithmetic, missing information, a source-embedded instruction, real guide retrieval in EN/PT/ES, a forced 16-token limit, oversized conversation history, controlled relevant guide sections in EN/PT/ES, a linked manual whose contents are absent, and an inventory with no documented power supply. Qwen3.5 gets an additional thinking-on case. Human review must distinguish citation presence from whether the cited passage actually supports the claim.

Results, full supplied source passages, answers, timing, generation metadata, and server logs are written to `output/model-tests/` (ignored by Git). Running again overwrites those model result files. The script deliberately reports outcomes instead of treating plausible prose as an automatic factual pass. Compare results only with the runtime version and hardware recorded alongside them; model versions, prompt caching, thermal state, and CPU scheduling affect latency.

For a comparison after retrieval or prompt changes, preserve prior outputs and omit the slow thinking case with `python -B tests/manual/real_models.py --skip-thinking-case --output-prefix retrieval-update-`. Review the supplied passages and each claim alongside citation coverage.

## Tier and quantization comparison

The pinned public artifacts in `tier_manifest.json`, `tier_extra_manifest.json`, and `unsloth_manifest.json` record the additional CPU comparison. Install the runtime and download artifacts with the same integrity-checked procedure above, substituting the manifest path. Model weights are ignored by Git and must never be committed.

For each manifest, run the eight source-following cases with:

```text
python -B tests/manual/real_models.py --manifest tests/manual/tier_manifest.json --skip-thinking-case --output-prefix tiers- --max-tokens 512 --cases grounded_arithmetic,missing_information,source_instruction,link_not_evidence,unsupported_power,controlled_kit_en,controlled_kit_pt,controlled_kit_es
```

Substitute `tier_extra_manifest.json` for LFM3 and `unsloth_manifest.json` for the paired quantizations and official Qwen3.8. Each manifest's `generation` object supplies the tested per-model sampler controls. The catalogue can also provide sampler defaults by exact filename. Explicit backend/model overrides win over catalogue defaults. The output cap is 512 for this concise-answer comparison; it does not change the application's 2,048-token default.

For a user-provided model, create an untracked manifest containing `id`, `file`, `path` (the existing absolute file path), `size_bytes`, `sha256`, and optionally `generation`. The harness reads and hashes that file in place; it does not copy, move, or modify it. Keep local paths out of published manifests. Decision models are outside this chat-generation comparison.

## Kiwix retrieval evaluation

`retrieval_manifest.json` freezes 59 natural questions: 22 original API cases, the electrical browser case, 24 held-out variants and 12 negative/ambiguous cases. Thirty currently have inspected target-section annotations; remaining coverage and human relevance labels are explicitly pending. Do not treat missing annotations as successful abstention or use the held-out cases for vocabulary tuning.

```sh
python3 -B tests/manual/retrieval_eval.py --manifest tests/manual/retrieval_manifest.json --output /tmp/retrieval-eval.json
```

The default run uses production retrieval and prompt construction, including read-only token fitting when the existing backend is available. It does not generate answers or start a model. Results record natural questions, actual query attempts, archive versions, fetch/filter outcomes, sources, prompt inclusion and target-section matches. `--settings FILE` supplies isolated settings overrides; `--limit N` is only a smoke run. `--generate` additionally generates answers and captures production fitting; use it only after retrieval gates pass and review critical cases repeatedly.

Target-section matching is narrower than a complete human relevance judgment. The tool deliberately leaves human precision and answer-safety approval unset and never marks release gates passed automatically. Generated reports may contain private prompts and source passages; only save/share them deliberately. The release target remains at least 90% annotated supported-case recall and 90% independently judged included-passage relevance, with no serious new answer-safety regression.


## Relevance follow-up validation

Run `python3 -B tests/manual/relevance_validation.py --output /tmp/relevance-validation.json` for the 24-case EN/PT/ES follow-up set. It uses production retrieval and read-only token fitting, without generation. Report topic/intent checks separately from passage applicability and clinical accuracy. The older 59-case manifest remains unchanged and is now observed regression data. See [the follow-up report](../../docs/reviews/2026-11-25-relevance-followup.md).

## Answer quality

The [emergency-advice eval](../evals/emergency_advice/README.md) runs actual questions against a running installation and supports evidence-based review of usefulness, unsafe instructions, semantic citation support, and unnecessary withholding. It is separate from retrieval scoring. The suite and its historical baselines stay in Git and are excluded from installation archives.
