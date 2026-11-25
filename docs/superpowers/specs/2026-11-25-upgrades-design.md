# Component upgrades and recovery

Status: approved by user; implemented capabilities and remaining manual boundaries are documented in `docs/upgrades.md`. No installed components were updated during implementation.

## Goal and approach

Provide an optional pre-start update check and a standalone maintenance command for Git and non-Git kits. Preserve offline operation, personal knowledge, local settings and a working previous version. An update check must distinguish an available update from an unreachable provider or an unidentifiable installation.

Recommended: a shared Python coordinator with explicit procedures for app, models, managed runtimes and libraries. Keep launchers thin so Linux, macOS and Windows have the same behavior. Reuse verified download and extraction helpers where their guarantees suffice; do not call the complete `prepare` workflow to upgrade a selected component.

Alternatives: shell-only scripts would duplicate platform and recovery logic; wrapping `prepare --resume` is smaller but mixes component selection, setup and runtime refresh and lacks durable rollback. Neither meets the requested scope.

## User interface

Proposed commands (also forwarded by run.bat/run.command):

```sh
./run.sh --check-updates          # report only, then exit
./run.sh --upgrade                # check, select, confirm, upgrade, exit
./run.sh --upgrade --component app
./run.sh --upgrade --component model
./run.sh --upgrade --component llama
./run.sh --upgrade --component kiwix-data
./run.sh --rollback TRANSACTION_ID
./run.sh --no-update-check        # start immediately without checking
```

Canonical Python subcommands `check-updates`, `upgrade` and `rollback` back these aliases. Additional component choices cover Kiwix tools, portable Python, bundled CUDA libraries and extraction tools. A drivers entry reports host-managed status and compatibility guidance.

For ordinary interactive startup, check at most daily with a total network deadline of five seconds. Contact actual metadata providers over HTTPS rather than using ping or a generic connectivity probe. Run independent checks concurrently within that deadline. Report partial availability honestly. Cache results with timestamps; do not label stale or failed checks current. Offer available updates before launching, with **Start now** as the default. Offline, timed-out or declined checks continue startup. Never check during `ask`, `chat`, `search`, or ordinary noninteractive startup. Allow a persistent opt-out.

Standalone checks can use a longer bounded deadline. Show installed and candidate identities, provenance, platform, download and temporary storage estimates, dependencies and restart requirements. Select components explicitly; updates never run merely because the machine is online. Noninteractive application requires explicit components and confirmation flags; no implicit update-all. Check output supports JSON with stable statuses: current, available, unknown, unavailable, blocked, manual.

## Discovery and identity

Record an installation manifest and per-component provenance: app commit, Git branch/upstream or source archive identity; model logical ID, revision and hash; runtime tag, asset and platform/backend; ZIM logical collection, language, variant, edition and checksum; index format/extractor version. Existing manifests and actual installed files establish inventory. Unknown custom files remain custom, not replaceable by guessing their filenames.

App candidates use the configured upstream branch for Git and the official main branch for standalone kits, matching current distribution. Resolve the candidate to an immutable commit before planning or download. Display that these are main-branch builds, not certified releases. Model and pinned-tool candidates come from project-maintained metadata at an immutable app commit; detect newer upstream artifacts separately but do not automatically select unreviewed weights. A model-family or quantization change is a separate choice, not a routine revision update. Kiwix candidates match the installed collection, language and variant; fixed historical archives remain fixed.

Check-only mode never replaces installed files or runs downloaded code. Metadata is bounded and parsed as data. Candidate identities are fixed in the approved transaction plan, preventing a moving branch/catalog from silently changing the approved update.

## Separate component procedures

| Component | Update and verification | Recovery |
|---|---|---|
| Git app | Inspect branch/upstream, tracked edits and untracked path collisions. Fetch and allow only an explicitly reviewed fast-forward from the recorded commit. Refuse dirty/diverged automatic updates; explain how to resolve them. Stage candidate and check syntax/config compatibility before activation. | Record previous commit and a recovery ref, plus affected settings. Refuse rollback over subsequent user edits; preserve them and provide a recovery checkout. Never auto-stash, force-reset or clean. |
| Standalone app | Download source at the resolved commit; validate archive paths and inventory. Replace only manifest-owned files; detect locally modified/deleted owned files and new path collisions before applying. Remove obsolete owned files only when unchanged and backed up. | Keep previous owned files and manifest; use a write-ahead journal to restore exact affected paths after partial activation. Preserve unrelated files. |
| Models | Download beside the active model; verify expected size and SHA-256, inspect compatibility/context and memory estimates, then run a bounded load/generation check with the selected runtime. Preserve explicit sampler settings and preview any required change. | Keep old weights and settings; switch selection back without redownload. Do not overwrite a same-named file in place. |
| llama.cpp and bundled CUDA | Stage a matching platform/backend build and companion libraries from the same release; verify available publisher digests and record verification strength; test executable and active-model compatibility. Missing trusted digest requires an explicit weaker-verification decision. | Retain the complete prior engine/library directory. Restore as a unit. |
| Kiwix tools, portable Python, extraction tools | Stage independently; verify pinned artifacts and test supported versions and capabilities. Python activation uses a separate helper so the running interpreter is not replaced in place. | Keep prior runtime; an independent recovery entry point must work if the candidate Python/app cannot start. |
| Host GPU drivers/system packages | Detect what can be established locally and report runtime compatibility or unknown status. Provide platform/vendor-specific manual update, backup and rollback instructions; no automatic sudo/package-manager/driver installation. | OS/vendor procedure; do not claim app-level automatic rollback of a host driver. |
| Kiwix data | Stage verified newer editions; validate ZIM integrity and representative reads, compare collection coverage, build versioned indexes when required, and review version-scoped source policy mappings. | Move superseded managed editions out of the served `zim/` directory into backup storage; restore archive selection and index together. Never serve old and new editions accidentally. |

For legacy standalone kits with no baseline manifest, attempt identification against an immutable upstream file manifest. If identity cannot be established, offer a reviewed baseline import showing every collision and backup; never assume an existing file is pristine. Modified bundled knowledge is treated as local content and blocks automatic replacement of that path. Personal knowledge, local precedence policies and settings are never erased by an app update.

Externally configured model/Kiwix services are reported as externally managed. Do not replace unrelated processes or remote services. Portable multi-platform kits show per-platform inventory; default upgrades target this host, with explicit selection for other platforms. Execution checks for foreign platforms are reported as not run.

## Transaction, backup and rollback

Use one installation maintenance lock shared by upgrade and preparation; coordinate with app startup and managed processes. Discovery may run while the app is active, but activation requires affected services stopped. Do not kill arbitrary processes occupying configured ports.

Persist a transaction directory outside scanned knowledge/model/ZIM locations with an approved plan, before/after inventories, backups and a flushed journal. States are planned, downloading, verified, activating, checking, committed, failed and rolled_back. Record each file operation before execution and recovery progress afterward. Check free space for downloads, extraction, old and new assets and indexes; do not discard a backup to make room without explicit cleanup.

Stage all selected dependencies before activation. Group model/runtime and archive/index dependencies into a single recoverable unit. Independent updates get separate transaction results. On activation or health-check failure, restore the affected unit and report both the failure and rollback outcome. On interruption, the next launcher detects the journal and offers recovery before executing partially installed code. The recovery helper and instructions live with the backup and cannot depend solely on the new app modules.

Retain at least the last working version; backup deletion is a separate explicit operation. Rollback verifies backup integrity and detects later user changes before restoration. It must work offline. Log identities and errors, never credentials or personal knowledge contents.

After an app/runtime update, start a fresh process using the committed code/interpreter; do not continue running imported old modules against new files. Preserve original launch arguments and prevent recursive update checks.

## Verification and limits

Automate disposable Git and standalone fixtures covering clean upgrades, dirty/diverged repositories, unknown baselines, changed/deleted bundled guides, personal files and settings, malicious archive paths, checksum mismatch, unavailable providers, low disk space, lock contention, interrupted activation and offline rollback. Inject failures between file operations and verify original byte hashes after recovery.

Use local fake metadata/download servers for deterministic tests. Test actual launcher arguments, noninteractive behavior, timeout budget and fresh-process handoff. Test model/runtime dependency failure, ZIM/index pairing, backup exclusion from retrieval and rollback refusal over newer user edits. Assert selecting app alone never refreshes llama, models or libraries.

Health checks establish operational success, not emergency-advice quality. Record advice evaluation as passed/failed/not run separately. The durable clinical-quality eval is a separate pending work item; until available, preserve the documented manual replay procedure and never imply an upgrade has passed it. Preserve inventory identities for future comparisons.

## Delivery order

1. Inventory, check-only CLI, provider adapters and optional startup offer; no destructive updates.
2. Transaction/recovery foundation, then Git and standalone app procedures and documentation.
3. Managed runtimes and model upgrades with compatibility checks and rollback.
4. Kiwix edition/index upgrades, source-policy review, host-driver procedures and full cross-platform verification.

Each milestone needs tests and documentation. Do not advertise unsupported application modes as working; show explicit manual/unsupported status until implemented. First-time setup remains for initial preparation, not the upgrade procedure.
