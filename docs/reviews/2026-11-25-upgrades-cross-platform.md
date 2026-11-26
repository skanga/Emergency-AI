# Cross-platform upgrade implementation and verification

The initial audit of `58256a9` found Windows transaction failures, macOS test assumptions and Linux-only external-tool catalogs. The implementation now supports native Windows, macOS and Linux upgrade/recovery paths. All nine final native CI jobs passed; evidence is recorded below.

## Changes

- File activation flushes a writable descriptor before copying metadata. Windows read-only targets can be replaced and restored; failed replacement restores the attribute, and interrupted recovery recognizes only the precisely matching temporary attribute state. Committed transactions still reject later user edits and backup verification remains exact.
- Windows maintenance leases use `LockFileEx` for real shared readers and exclusive writers. Cross-process tests verify exclusion and subsequent release.
- Windows restart arguments are quoted for the CRT. Redirected startup does not mistake Windows NUL for an interactive terminal. Actual host launchers are exercised from directories containing spaces, including maintenance arguments and an external root.
- CLI, migration and interrupted-start recovery print the retained recovery helper with explicit target root and native command quoting, without needing application imports during recovery.
- Kiwix pins now cover Linux x86_64/ARM64 and macOS Intel/Apple Silicon at 3.8.2, and Windows x86_64 at 3.8.1. Flat Windows ZIP layout is supported.
- Xpdf 4.06 pins now cover Linux x86_64, Windows x86_64 and both macOS architectures. Windows `.exe` version output and `.txt` documentation are handled, and all license files remain intact.
- Fixtures now use native executable names, explicit platform metadata, resolved paths, closed SQLite handles and platform-appropriate permission assertions. Git CRLF and clean/smudge filter regressions preserve exact rollback and later-edit protection; no Git staging change was necessary.
- CI pins Node before Python tests that invoke it. A scheduling-sensitive retrieval assertion now uses events to verify that a request returns while its worker is blocked; forcing blocking executor shutdown makes this test fail.

## Repeatable validation

The ordinary suite runs in nine native OS/Python jobs: Linux x86_64, Windows x86_64 and Apple Silicon macOS with Python 3.11 and 3.14; Linux ARM64 and Intel macOS with 3.11; Windows ARM64 with 3.14.

Five Python 3.11 jobs additionally download native tools into disposable installations and exercise real executable checks, activation and offline rollback. Primary executables are made read-only before the test; transaction journals prove actual replacement, and snapshots prove complete byte and permission restoration. Python checks SSL, SQLite and application CLI imports; llama CPU checks executable health without a model; Xpdf extracts known PDF text and runs pdfinfo; Kiwix checks its executable. Unsupported Linux ARM64 Xpdf is explicitly skipped.

Native runtime metadata is pinned to official llama b12751 and Python build 20261124 in `tests/fixtures/native-runtime-releases.json`. The fixture records publisher size/SHA-256 and source release URLs. Tests use the actual selection code and verified HTTPS artifact downloads, but make no GitHub metadata API calls. This avoids shared-runner API rate limits and changing the test release whenever upstream publishes. It does not change application update discovery.

Commands:

```sh
python -B -m unittest discover -s tests
EMERGENCY_NATIVE_TOOL_TESTS=1 python -B -m unittest tests.test_native_tool_upgrades tests.test_native_runtime_upgrades -v
```

On PowerShell, set `$env:EMERGENCY_NATIVE_TOOL_TESTS='1'` first. The workflow automates both suites on the appropriate hosts. Shell syntax checks and the retrieval UI JavaScript suite also pass locally.

## Boundaries

- Windows ARM64 has native core/launcher/recovery test coverage; real downloaded runtime integration tests cover the other five host architectures. No native Kiwix/Xpdf package is pinned for Windows ARM64. Linux ARM64 Xpdf also remains manual.
- Tests replace the same verified release, rather than claiming compatibility with every historical release. GPU execution/driver changes, large-model inference and native ZIM content reads are outside these new CI checks. Installed ZIM health checks still run when real archives are present.
- Tool SHA-256 pins are project-reviewed artifact identities, not publisher signatures. New unreviewed tool releases remain manual. Indexed documents and edition-specific policies retain their existing migration gates.
- No user installation, local knowledge, model, archive or index was changed. CI uses temporary installations; the feature worktree remains available for review and commit.

## Evidence

The pre-fix run [45722592746](https://github.com/skanga/Emergency-AI/actions/runs/45722592746) passed both Linux jobs but failed both Windows jobs (7 failures/40 errors each) and both macOS jobs (7 failures/3 errors each).

Run [45725850717](https://github.com/skanga/Emergency-AI/actions/runs/45725850717) passed all nine jobs, including real executable replacement and permission-preserving rollback. Final run [45726456296](https://github.com/skanga/Emergency-AI/actions/runs/45726456296) also passed all nine jobs on snapshot `b73674f4191b8745f08bbd7ff5c1183b24c901a9`, including the pinned metadata and deterministic test harness. Each ordinary job ran 617 tests. Five jobs additionally ran the native integration suite (five tests, including offline metadata selection); Linux ARM64 explicitly skipped only its unavailable Xpdf artifact. Full job summaries are in `2026-11-25-upgrades-cross-platform-evidence.json`.
