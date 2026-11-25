# Python upgrade completion

Updated `/home/skanga/Emergency` from CPython 3.12.16 build 20261110 to build 20261124, using `/usr/bin/python3` outside the target runtime. The official pinned archive was verified at 68,209,387 bytes and SHA-256 `6774c7f49ee21c1723f7ac91961a5bf9f3ee3ae6e4d82ff58bd358958b546461`. Authenticated GitHub metadata was saved and reused for both test applications; download validation and the normal CLI/transaction checks remained active.

The previous blanket symlink blocker is replaced with validation of internal file links, reusing llama's exact link-preserving transaction backups. Escaping, broken and directory links remain blocked. Staged and activated interpreters check SSL, SQLite and application CLI imports under isolated, bytecode-free execution. An independent-interpreter guard still prevents replacing the interpreter executing the upgrade.

The first live staging attempt revealed repeated gzip decompression when resolving the distribution's 1,049 links. It was canceled before any transaction or activation. Materialization now decompresses once into a private temporary raw archive, then uses the existing path/link validation and materialization. The added regression fails when decompressor rewinds return. This uses additional temporary space equal to one decompressed archive; cleanup runs before any failed staging can affect installed files.

Completed upgrade, real interpreter and app UI/status/guides/search checks, offline rollback through the retained recovery helper, then exact restoration verification. All 9,621 recorded paths matched the original snapshot, including the original Python links. Reapplied the upgrade and repeated health checks. Final comparison found 2,867 changed paths, all inside the managed Python runtime or `runtime/installation.json`; app ownership, model/Kiwix provenance, configuration and knowledge stayed unchanged. Snapshots exclude logs, bytecode caches and retained upgrade transactions. The app is stopped, Python 20261124 remains installed, and no transactions are pending recovery.

- Tested rollback: `cf163f94bce94eec9e1b1d081c6d34fb`.
- Final committed transaction: `7d4ff34014674b528d4d930a747e9b4d`.
- Full suite under system Python: 585 tests, 16 skipped, zero failures/errors.
- Full suite under the newly installed bundled Python: 585 tests, 16 skipped, zero failures/errors.
- Independent review found no blocker for this inspected installation or the gzip staging fix. Targeted safety/rollback/no-rewind tests passed. Diff checks passed.

The managed Python tree is replaced as a unit. User-added packages/scripts inside it are not automatically migrated; the inspected installation contained only bundled pip. App smoke checks used `--no-engines`, and no advice-quality evaluation was performed.

[Structured evidence](2026-11-25-python-upgrade-evidence.json). Detailed snapshots, public release metadata, upgrade/recovery logs and interpreter checks are in `/tmp/python-upgrade-test`.
