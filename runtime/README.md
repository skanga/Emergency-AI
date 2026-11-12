# runtime/

Engines downloaded by `prepare-kit`, organized by platform:

- `llama.cpp/<platform>/` — AI model server (`llama-server`)
- `kiwix-tools/<platform>/` — library server (`kiwix-serve`)
- `python/<platform>/` — portable Python

`<platform>` is windows-x86_64, windows-arm64, linux-x86_64, linux-arm64, macos-arm64 or macos-x86_64.
A `llamafile` executable can also be placed directly in this folder.
