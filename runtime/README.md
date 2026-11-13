# runtime/

Engines downloaded by `start prepare`, organized by platform:

- `llama.cpp/<platform>/` — AI model server (`llama-server`)
- `kiwix-tools/<platform>/` — library server (`kiwix-serve`)
- `python/<platform>/` — portable Python

`<platform>` is windows-x86_64, windows-arm64, linux-x86_64, linux-arm64, macos-arm64 or macos-x86_64.
A `llamafile` executable can also be placed directly in this folder.

When preparing a kit with an AI model, the preparer checks the newest available llama.cpp releases for a binary matching each selected platform, even if an engine is already installed. It records the installed tag and asset in `llama.cpp/<platform>/release.json`, skips re-downloading the current build, and replaces older or unversioned installations. Updates are extracted separately before replacing the working engine. If the online check fails, setup reports a failure rather than claiming the installed version is current.

Starting the kit offline does not check for or download updates.

`kit-info.json` records whether the last requested preparation completed and lists component results. Failed downloads remain in `_downloads/` as `.part` files for retry. Models, ZIMs, runtimes, logs, local settings and extra personal guides are excluded from Git by `.gitignore`.
