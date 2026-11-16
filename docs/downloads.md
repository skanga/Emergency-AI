# Downloads and models

[Home](../README.md) · [Getting started](getting-started.md) · [Using the app](using-emergency-ai.md) · [Downloads](downloads.md) · [Help](troubleshooting.md) · [Reference](technical-reference.md)

Downloads are optional. The included guides work without an AI model or extra reference libraries. Run setup while you still have internet.

## Choose a starting point

| You want to… | Choose |
|---|---|
| Read and search the included guides | No model and no extra libraries. |
| Try AI with the smallest recommended model download | `lfm3-1.7b`; 8 GB system RAM recommended. |
| Add a small collection of reference books | The `minimal` library profile. |
| Add repair and energy references | The `recommended` library profile. |

An AI model generates text. A library contains reference material to read and search. Download sizes for these two choices are separate; neither includes all the software or temporary installation space.

## Add or repair downloads

Open a terminal in your Emergency AI folder. These commands work in Windows Command Prompt or PowerShell, or in a Linux/macOS terminal.

| Action | Windows | Linux / macOS |
|---|---|---|
| Choose downloads | `.\run.bat prepare` | `./run.sh prepare` |
| Resume saved choices | `.\run.bat prepare --resume` | `./run.sh prepare --resume` |
| Repair only this computer | `.\run.bat prepare --resume --os this` | `./run.sh prepare --resume --os this` |
| Check installed components | `.\run.bat status` | `./run.sh status` |

Restart the app after adding libraries. If you manage Kiwix separately, load the new libraries in that server too.

## Library profiles

Kiwix is the software that reads downloaded libraries. Its library files end in `.zim`.

| Profile | Includes | Approximate library download |
|---|---|---|
| `minimal` | English medical encyclopedia, field medical and post-disaster manuals, water, food, and knots | 3 GiB |
| `recommended` | Minimal plus Portuguese/Spanish medical Wikipedia, iFixit, Appropedia, and Energypedia | 8 GiB |
| `full` | Recommended plus Wikipedia without images in EN/PT/ES and English Wikivoyage | 77 GiB |

Sizes change with new editions. Add the model download, software, and room for extraction and updates when planning disk space. A full installation can require more than 100 GB. The app checks space during setup; a library profile's size is not the total installation size.

Choose `none` to skip extra libraries. Archived libraries are separate and never included automatically, even in `full`.

## Model choices

These are the recommended starting points from our CPU source-following tests, not a claim of universal best accuracy. All choices run text-only with thinking off by default. Downloads are optional and model weights never go into Git.

| Use | Model ID | GGUF download | Recommended system RAM | License |
|---|---|---:|---:|---|
| Lightweight / default | `lfm3-1.7b` | ~1.1 GB | 8 GB | LFM Open License v1.0 |
| Balanced | `gemma4-e2b` (Unsloth UD-Q4_K_XL) | ~3.2 GB | 16 GB | Apache 2.0 |
| Larger CPU model | `qwen35-9b` | ~6.2 GB | 24 GB | Apache 2.0 |

RAM figures include estimated operating-system headroom and are recommendations, not validated minimums. Tests ran on a 64 GB Windows computer. Gemma's E2B name refers to effective computation; its total weights are larger. The app does not automatically choose a model based on your RAM.

For a lightweight Apache-licensed alternative, choose `qwen35-2b`. `qwen3-4b` offers a smaller balanced download and a non-thinking model; `ministral3-8b` is another larger option. `qwen38-27b` offers official Qwen3.8 27B in Unsloth UD-Q4_K_XL (~17.7 GB download, 32 GB RAM recommended); it is much slower on CPU and is an advanced option, not the default. The preparation menu lists only the current models. Old model IDs have been removed; choose a current model with `.\run.bat prepare` (Windows) or `./run.sh prepare` (Linux/macOS) if an existing setup refers to a removed ID. New setup selects `lfm3-1.7b` (option 1, the smallest download) by default, including unattended setup. The interactive menu detects total system RAM on Windows, Linux, and macOS and compares it with each model's RAM recommendation. If detection fails, recommendations still appear. These estimates describe the current computer and do not guarantee fit: context size and other applications also use memory. Larger models remain selectable, including when preparing a kit for another computer. To change an existing kit explicitly, run `.\run.bat prepare --model gemma4-e2b` on Windows or `./run.sh prepare --model gemma4-e2b` on Linux/macOS.

Sampler presets accompany the verified filenames, so model-specific sampling is used during normal llama.cpp inference. Explicit backend/model settings take priority. Weights are pinned to artifact revisions and hashes; the separate llama.cpp runtime is still refreshed to the latest compatible release on preparation.

See the [tier comparison](model-tier-evaluation-2026-11-13.md) for the tested candidates, quantizations, local-model observations, and remaining source-fidelity errors. A larger model or a different quantizer does not guarantee a better answer. The bundled source content still needs the review recorded in [content review backlog](../TODO.md).

## Optional archived libraries

These are **historical snapshots**, separate from the current catalog downloads. They are never selected by `--yes` or any `--zims` profile. Setup, the saved kit manifest, and the assistant's source citations identify archived libraries and their dates. If a library has no date in its name or publication metadata, citations say that its snapshot date is unknown.

| Selection ID | Library | Archived edition | Download size | Hosted by |
|---|---|---|---|---|
| `wikem` | WikEM, English | **June 2020** | 60 MiB | [Internet Archive](https://archive.org/details/wikem_en_all_maxi_2020-06.zim) |
| `wikihow-en` | wikiHow, English | **March 2023** | 47.7 GiB | [Kiwix archive](https://archive.download.kiwix.org/zim/wikihow/) |
| `wikihow-es` | wikiHow, Spanish | **September 2024** | 25.3 GiB | [Kiwix archive](https://archive.download.kiwix.org/zim/wikihow/) |
| `wikihow-pt` | wikiHow, Portuguese | **October 2024** | 10.4 GiB | [Kiwix archive](https://archive.download.kiwix.org/zim/wikihow/) |

**WikEM is an old medical reference for clinicians, not current clinical guidance.** All four collections may contain outdated instructions. The dates describe the saved editions, not when you download them. Selecting them again keeps those fixed editions; it does not refresh their content.

To add only the archived WikEM copy to an existing kit:

**Windows (PowerShell):**

```powershell
.\run.bat prepare --model none --zims none --archives wikem --os this --yes
```

**Linux / macOS:**

```sh
./run.sh prepare --model none --zims none --archives wikem --os this --yes
```

Use `--archives wikem,wikihow-en` for selected archives, or `--archives all` for all four (about **83.5 GiB**). Omit `--archives`, or use `--archives none`, to skip them. Skipping an archive does not remove a previously downloaded copy; move its `.zim` file out of `zim/` if you no longer want it searched. Extra archived editions do not replace other installed editions.

Archive downloads resume after interruptions. Before a file becomes available to Kiwix, the `prepare` command checks its exact size, ZIM header and embedded MD5 checksum. These checks detect corruption; the embedded checksum does not authenticate the publisher. No published SHA-256 was found for these archived copies. Checking a large file can take several minutes. The direct URLs, byte counts, dates and source pages are recorded in [config/zims.json](../config/zims.json).

## Advanced preparation

Your latest setup choices are saved in `runtime/setup.json` before downloads begin. `--resume` reuses the saved choices and platforms. Use `--os this` to repair only this computer. Startup checks installed files and configured services instead of trusting a previous successful setup on another machine. These are quick presence and size checks; full download integrity checks happen during preparation. An available configured Ollama/OpenAI-compatible service can provide the AI without a bundled model. Restart the app after adding libraries; an independently managed Kiwix server must also load the new files.

The active Kiwix profiles contain 15 catalog entries. WikEM and wikiHow are absent from the current official catalog (checked November 12, 2026), but older copies are available as [optional archived libraries](#optional-archived-libraries). Archives are excluded from every profile, including `full`. Profile sizes above exclude the model and runtimes and change with upstream releases.

The `prepare` command starts with **Recommended choices** (default) or **Advanced models and archived libraries**. Recommended shows the three starting models and guide-only mode; archived libraries and alternative models appear only in Advanced. Explicit command-line model/archive selections remain available. The remaining choices are:

1. **AI model:** `lfm3-1.7b` (lightweight/default, ~1.1 GB download, 8 GB system RAM), `gemma4-e2b` (balanced, ~3.2 GB, 16 GB RAM), or `qwen35-9b` (larger, ~6.2 GB, 24 GB RAM). See [model choices](#model-choices) for licenses and alternatives.
2. **Kiwix libraries:** `minimal` (~3 GiB), `recommended` (~8 GiB) or `full` (~77 GiB, Wikipedia without images).
3. **Optional archived libraries:** older WikEM/wikiHow snapshots; **None** is the default. Each option shows its date and size.
4. **Systems:** this computer only, or **Windows + Linux + macOS** (universal USB kit).
5. **Portable Python:** setup lists completed runtimes it will reuse. If every selected platform already has Python, it skips the question. Otherwise it asks only about downloading or repairing the missing platforms; declining keeps the existing runtimes.

Non-interactive:

**Windows (PowerShell):**

```powershell
.\run.bat prepare --model gemma4-e2b --zims recommended --os all --python
```

**Linux / macOS:**

```sh
./run.sh prepare --model gemma4-e2b --zims recommended --os all --python
```

For GPU downloads, update behavior, and integrity checks, see the [technical reference](technical-reference.md#acceleration-and-updates).
