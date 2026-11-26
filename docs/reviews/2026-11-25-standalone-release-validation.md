# Standalone merged-release installation and rollback validation

Upgraded `/home/skanga/Emergency` from `ff7055b085851c6543adac2511d0259d2affe488` to the published, merged application commit **`d22579a2f154405cb5fc2d959b9b6aa0fb22ad47`** through the normal external updater CLI. Completed upgrade, validation, offline rollback, exact restoration verification, reapplication and final validation.

## Preservation and rollback

A complete copy of the approximately 19 GiB kit is retained at `/tmp/standalone-release-validation/kit-before`. Its 9,621 recorded file/link paths were verified against the before-upgrade snapshot. The application was stopped before maintenance.

- First upgrade transaction: `cfff52ac22104eaa990d2a704f30b98b`.
- Invoked its retained `recover.py` directly for offline rollback; it restored all **9,621 recorded paths with zero differences** in file bytes, file permission modes and symlink targets. The restored application also passed startup, UI, guide and search checks.
- Final reapplied transaction: **`a8097307eb94440e90bae15ff76d1d11`**.
- Final snapshot contains **9,645 paths**, with **30 changed/added paths**, all confined to application-owned files and `runtime/installation.json`. Every one of the 94 final owned files matches its recorded hash. All 52 preserved configuration/knowledge files, models, ZIM archives, indexes, runtime binaries and existing component provenance remained unchanged.
- The installed updater reports the application **current**, and there are **no pending recovery transactions**. The application is left **stopped**, matching its initial state.

Snapshots exclude logs, bytecode caches and retained upgrade journals. Directory timestamps and newly created empty directories are not part of file restoration assertions. Transaction backups and the whole-folder backup are retained.

## Operational validation

- Installed launcher starts the web application on loopback; UI and status endpoints respond.
- All 45 built-in guides are listed: 15 each in English, Spanish and Portuguese. Search returns results in all three languages.
- The installed launcher's `--upgrade --help` works. A concurrent maintenance attempt during the engine probe was correctly blocked by the installation lock; it passed after the probe released its lock.
- CPU, CUDA and Vulkan llama backends at their unchanged `b12719` build each loaded the installed Qwen model, returned healthy and generated one token, both after the first upgrade and after final reapplication. Every temporary engine process was stopped afterward.
- The bundled Python imports SSL and SQLite successfully.
- All three recorded Kiwix executable files and all 35 Xpdf distribution files match their prior provenance. Xpdf 4.06 passes actual synthetic PDF extraction and pdfinfo checks.
- Kiwix tooling reads metadata for all ten installed ZIMs into a temporary library. Direct reads of each archive's main entry succeed.
- Actual Kiwix HTTP requests for all ten archive main pages return HTTP 200 using an **IPv6 loopback-only** listener. No all-interface listener was needed, and the server was stopped after the checks.

The UI smoke tests used `--no-engines`; engine and archive HTTP checks were performed separately. This is operational installation/recovery validation, not an end-to-end emergency-advice evaluation. One-token generation is not a performance or GPU-acceleration benchmark. No model/runtime/data upgrade was applied in this task, and locally owned catalogs were intentionally preserved.

## Start or roll back

Start the updated installation normally:

```sh
/home/skanga/Emergency/run.sh
```

To restore the pre-upgrade application later, first stop the application and its managed services, then use the retained recovery helper:

```sh
/usr/bin/python3 /home/skanga/Emergency/runtime/upgrades/a8097307eb94440e90bae15ff76d1d11/recover.py \
  --root /home/skanga/Emergency \
  --rollback a8097307eb94440e90bae15ff76d1d11
```

Rollback intentionally refuses conflicting later edits. Keep the whole-folder backup and transaction directory until the updated installation has been accepted.

[Structured evidence](2026-11-25-standalone-release-validation-evidence.json). Detailed snapshots and startup/engine/upgrade logs are retained under `/tmp/standalone-release-validation`.
