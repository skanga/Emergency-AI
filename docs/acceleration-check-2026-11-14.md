# CUDA and Vulkan local comparison

Tested on Windows x86-64 with an NVIDIA RTX PRO 2000 Blackwell Generation Laptop GPU, driver 597.30, llama.cpp b12376, and its CUDA 13.5 package. CUDA's companion runtime libraries were bundled beside the executable in an isolated test installation.

Both backends used the same NVIDIA GPU; the Intel integrated GPU was excluded. The model was the already-installed `LFM3-1.7B-Q4_K_M.gguf`, with a 4096-token context, 128 generated tokens per request, temperature 0, seed 42, thinking disabled, and prompt caching disabled. Each backend handled three sequential requests for a short explanation of how a bicycle works.

| Backend | End-to-end tokens/s, three runs | Median |
|---|---|---|
| CUDA | 138.80, 140.39, 135.28 | 138.80 |
| Vulkan | 90.85, 104.12, 103.20 | 103.20 |

CUDA's median end-to-end throughput was about 35% higher in this small check. Measurement includes prompt processing and HTTP response time, but excludes engine/model startup. Both backends produced visible text. This is evidence for trying CUDA first on this machine, not a general performance guarantee across models, drivers, or hardware. Linux and ARM64 CUDA inference were not exercised here.

Reproduce from the repository root, using Python or the kit's portable Python interpreter:

```text
python tests/manual/acceleration.py --download
```

The script downloads CPU, Vulkan, CUDA, and matching CUDA runtime libraries into `runtime/acceleration-check/`, leaves normal installed engines alone, uses temporary loopback ports, and stops its servers on completion or failure. It requires the model to be already installed. Downloads and extraction require several GB of free space. Omit `--download` to reuse the test runtimes; use `--model FILENAME.gguf` to compare another installed model.

Raw timings are saved in `runtime/acceleration-check/comparison.json`. The test runtime folder remains available for repeat measurements and is excluded from Git. The normal app still needs preparation with `--cuda` to install CUDA in its own runtime folders.
