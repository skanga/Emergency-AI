# External tool verification and upgrade handling

Completed managed Kiwix/Xpdf provenance and safe update handling for the inspected Linux x86_64 installation. Both installed tools already match the reviewed versions, so no replacement was necessary: Kiwix tools 3.8.2 and Xpdf tools 4.06. Real adoption, offline rollback and re-adoption passed. The normal upgrade command now reports both current without an implied download.

## Trust and discovery

Kiwix's [official release listing](https://download.kiwix.org/release/kiwix-tools/) and [GitHub release](https://github.com/kiwix/kiwix-tools/releases/tag/3.8.2) identify 3.8.2. The download site provides MD5 but no SHA-256/metalink for this artifact; GitHub supplies no native release assets. Downloaded the official archive with HTTPS and redirect verification enabled, cross-checked the publisher MD5, and reviewed/pinned exact bytes in `config/runtime-tools.json`: size 21,661,067, SHA-256 `b0ae98dd344aa0469a15ab42feff6d5aafb79541a82fb4e2647c74b073123815`. Automatic verification uses this project-reviewed SHA-256, not MD5. Provenance explicitly does not claim a publisher SHA-256 or signature. Future unreviewed versions/platforms remain manual.

Xpdf uses the existing project-reviewed 4.06 artifact pin: size 16,124,814, SHA-256 `940c137cbd1856e45813da1a25c12e8dd3dc8997b8ea735feb858684603031e3`. The official download host served identical verified bytes. The main website failed TLS certificate verification; validation was not disabled, and no claim is made that 4.06 is the latest upstream version. Discovery reports the current reviewed catalog version shipped with the updater.

## Preservation and capability checks

Explicit tool adoption downloads reference distributions, compares every installed distribution file, rejects extras/modifications, runs capability checks and records provenance in a transaction. It does not reinstall tools or modify archive/index data. Future updates recheck the recorded owned files before replacement and run pre/post health checks. Kiwix checks every installed ZIM; Xpdf checks version identity and real text extraction from a synthetic PDF. Existing document indexes permit unchanged-version adoption but block a newer extractor until reviewed index migration.

All three Kiwix binaries and all 35 Xpdf distribution files matched. Kiwix opened all ten installed archives and read each main entry. Xpdf extracted the expected text. Two real-world probe bugs were fixed: Kiwix on WSL rejects loopback and needs the same exact-error, WSL-only IPv4 fallback as the normal launcher (with explicit network notice and guaranteed process cleanup); Xpdf's successful version query returns 99, so the probe now requires an allowed exit code plus exact expected tool/version output before accepting it.

## Verification and final state

- Real provenance rollback transaction: `0d5429f0a4d941df957d8b56c4ac8e6d`.
- Final committed adoption transaction: `213fbf7777264d2da61af73f7d7b348a`.
- Across 9,621 tracked paths, rollback matched the original snapshot exactly. Final comparison changed only `runtime/installation.json`. Snapshots exclude logs, bytecode caches and retained upgrade transactions. Binaries, archives, indexes, settings, knowledge and other component/app provenance remained unchanged.
- Disposable fixtures also exercised an actual reviewed Kiwix version replacement, owned-file verification and rollback.
- Full regression suite under bundled Python: 595 tests, 16 skipped, no failures/errors. Earlier system-Python suite: 594 tests, 16 skipped, no failures/errors. Final CLI display/help tests: 14 passed.
- Independent review found and verified fixes for the WSL-only binding guard and subprocess failure reporting; no outstanding review blockers. Mutation testing caught removal of the installed-file integrity guard; production code remained unchanged. Shell syntax and diff checks passed.

The app is stopped and no recovery transactions are pending. Tool support is limited to reviewed artifacts/platforms; newer extractor/index migrations and host drivers remain manual. Operational checks do not assess advice quality.

[Structured evidence](2026-11-25-external-tools-evidence.json). Detailed public metadata, artifact/reference verification, snapshots and logs are under `/tmp/external-tools-upgrade-test`. [User procedure](../upgrades.md).
