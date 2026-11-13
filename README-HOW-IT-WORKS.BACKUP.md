# Original README explanation and diagram

To revert, replace the entire "How it works" section in both `README.md` and `README.en.md` with the section below. Keep the following horizontal separator and Quick start section in place.

## How it works

The kit combines **documents to read**, **software to search them**, and an optional **AI model to write answers**. You download the extra parts while you have internet, then use the saved copies offline. The included survival guides work without downloading a model or extra libraries.

See the [Glossary](#glossary) for explanations of the component names and file formats.

```
 Question ──► search kit guides ─────────────┐
          └─► search Kiwix (.zim files) ──────┼─► local language model ──► answer with [1] [2] sources
                                              └─► (no model? shows the most relevant passages)
```

| Part | What it is | Where |
|---|---|---|
| `survival.py` + `app/` | Application and search logic (Python standard library only, no `pip install`) | repository |
| `knowledge/pt|en|es/` | Survival guides in Markdown | repository |
| `knowledge/extra/` | **Your** `.md`/`.txt` documents (searched and cited by the AI) | repository |
| `runtime/llama.cpp/` | Engine that runs the AI model | downloaded by the preparer |
| `models/*.gguf` | Language model (1–5 GB) | downloaded by the preparer |
| `runtime/kiwix-tools/` + `zim/*.zim` | Kiwix server and libraries | downloaded by the preparer |
| `runtime/python/` | Portable Python (for PCs without Python) | downloaded by the preparer |

Keep downloaded models, libraries and runtimes out of git: the repository stays small and everyone builds their own kit with the preparer.
