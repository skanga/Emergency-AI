# Updating an existing Emergency AI kit

Use the upgrade commands for maintenance. First-time setup (`prepare`) chooses or repairs downloads; it is not the application upgrade procedure.

## Check and choose

On Linux/macOS use `./run.sh`; on Windows replace it with `.\run.bat`. Direct Python equivalents work too: `python3 emergency.py upgrade --component app`.

```sh
./run.sh --check-updates
./run.sh --check-updates --json
./run.sh --upgrade
./run.sh --upgrade --component app
./run.sh --upgrade --component model
./run.sh --upgrade --component llama
./run.sh --upgrade --component kiwix-data
```

An ordinary interactive launch checks at most once per day, with a five-second total discovery deadline. Enter starts immediately. Offline checks and unavailable providers do not prevent startup. Checks contact metadata providers; they do not download model weights or archives. Noninteractive startup and `ask`, `chat`, `search`, and `status` do not check online.

Use `./run.sh --no-update-check` to skip a startup check. To disable it persistently, add `"check_updates_on_start": false` to `config/settings.local.json`, preserving the other settings.

The report distinguishes **current**, **available**, **unknown**, **unavailable**, **blocked**, and **manual**. “Current” compares recorded versions; it is not a full disk-integrity or clinical-quality assessment. An offline provider is never reported as current. A custom component is never replaced merely because its filename resembles a known download.

The upgrade command shows the offered identities and download sizes before confirmation. Stop the app and its local engines before applying changes. It does not terminate processes. Automated use requires explicit selection and approval, for example `--upgrade --component app --yes`. Do app/Python updates separately; after either changes, restart the command before selecting other components. No implicit update-all is performed.

Each available artifact is a separate transaction. Model/runtime checks use the currently installed counterpart; jointly incompatible changes need a manual staged migration. Selecting several categories does not create one atomic group. Unknown/custom artifacts are listed as unchanged while verified peers can update. Temporary-space checks run during staging/activation; the displayed download size is not the full space requirement.

## Backups and recovery

Each applied component receives a transaction ID. Files, checksums, permissions, before/after inventory and a journal are retained in `runtime/upgrades/ID/`. These backups are outside the active model, knowledge and ZIM folders. Keep this folder when copying your kit. No automatic backup cleanup runs.

Allow space for the download, extraction, old files, retained new files and activation copies. Large-model and ZIM upgrades can need several times the artifact size temporarily. If space is insufficient, the upgrade stops; it does not delete old data to make room.

```sh
./run.sh --rollback TRANSACTION_ID
```

Rollback works offline, requires affected services stopped, and refuses to overwrite subsequent file edits. Roll back dependent updates in reverse order. After an interruption the launcher refuses to import a partially updated application and identifies the transaction needing recovery.

If application files or the top-level recovery script are damaged, use the independent helper saved with the transaction and an intact Python interpreter:

```sh
python3 runtime/upgrades/TRANSACTION_ID/recover.py \
  --root /absolute/path/to/kit --rollback TRANSACTION_ID
```

On Windows use an intact system Python (`py -3`) or an intact retained portable interpreter. Do not rely on a broken interpreter to repair itself. The helper needs only Python's standard library. Keep a separate copy of the entire working kit before host/OS maintenance or manually updating components.

## Application: Git checkout

The checker follows the checkout's configured GitHub upstream branch and resolves its candidate to a commit before activation. Official standalone builds follow `skanga/Emergency-AI` main; these are branch builds, not certified releases.

1. Save or commit your local source changes. Review `git status`; do not use reset/clean to discard them.
2. Run `./run.sh --check-updates`, then `./run.sh --upgrade --component app`.
3. The updater stages the candidate, checks source syntax/configs, and allows only a fast-forward. Diverged branches and file collisions require manual resolution. Ignored personal files are protected too.
4. The transaction retains the prior commit/ref, changed files, permissions and Git index for offline recovery. It does not stash your changes.
5. Start a fresh process and verify guides, model and libraries. Use the displayed transaction ID to roll back if needed.

Non-GitHub remotes and detached/unknown upstreams receive a manual status. Use your normal repository review workflow for those configurations.

## Application: standalone folder

Standalone upgrades update only files owned by the recorded application manifest. Personal guides, local settings, model weights, archives and unrelated files remain in place. Locally edited or deleted bundled guides block automatic replacement instead of being erased. Obsolete owned files are removed only after their existing content matches the baseline and a backup exists.

Older installations do not have `runtime/installation.json`. The first upgrade needs the **actual original source commit**:

```sh
./run.sh --upgrade --component app --baseline ORIGINAL_40_CHARACTER_COMMIT
```

The updater downloads that immutable baseline and checks its owned files against the installation. A mismatch stops the update. Do not substitute today's commit or assume a modified installation is pristine. Keep your whole-folder backup and reconcile modified files first. The preceding review installation was based on `ff7055b085851c6543adac2511d0259d2affe488`; use that only if it is the version you actually installed.

### Sparse or modified legacy installations

Use a separately checked-out updater that contains these commands. Choose a reviewed, published 40-character source commit. This procedure normalizes source ownership; it does not pretend that existing local configuration or knowledge matches that commit.

```sh
/tmp/emergency-ai-upgrades/run.sh --plan-migration \
  --root /home/skanga/Emergency \
  --commit ff7055b085851c6543adac2511d0259d2affe488 \
  --output /tmp/emergency-migration-plan.json

/tmp/emergency-ai-upgrades/run.sh --apply-migration \
  /tmp/emergency-migration-plan.json \
  --root /home/skanga/Emergency --yes
```

Review the plan's replacement/addition list before applying it. Omit `--yes` for interactive confirmation. Preview writes a new plan outside the target kit and does not replace installed files. Apply fetches exactly the pinned source again, compares the complete plan against current contents and permissions, and refuses stale plans. Git installations and already-owned application baselines use their normal upgrade procedures instead.

Existing files under `config/` and `knowledge/` stay locally owned, including bundled guides and catalogs. Future application upgrades **do not update these preserved files**; reconcile new defaults, catalogs and bundled-guide revisions separately with your local versions. Candidate source paths outside these folders are added or replaced only as listed; unrelated local files remain untouched. Model weights, ZIM archives, indexes and runtime binaries are outside application ownership.

Apply records the source-owned hashes and preserved paths in `runtime/installation.json`, retaining existing component provenance. It backs up every replaced file and the prior manifest, then verifies application CLI startup. Test the UI and local guides afterward; CLI startup is not an advice-quality evaluation. Failure rolls the transaction back. The success message prints an absolute command using the transaction's retained `recover.py` and explicit target `--root`, so offline rollback works even if the installed launcher predates upgrade support.

Once upgraded, the manifest records ownership and commit identity; later updates do not need `--baseline`. For an installation older than these commands, keep the new updater in a **separate folder** and point it at the old installation. Do not overlay updater files first: that would invalidate the old baseline.

```sh
python3 /path/to/new-updater/emergency.py upgrade \
  --root /path/to/existing-kit --component app \
  --baseline ORIGINAL_40_CHARACTER_COMMIT
```

The external updater stages the candidate and upgrades the target under its maintenance lock. Its `--root` option also works for checks, adoption and rollback. Keep a whole-folder backup first. Do not rerun the empty-directory installer into an existing kit.

## Models

For an older downloaded model, establish provenance once:

```sh
./run.sh --adopt --component model
./run.sh --check-updates
./run.sh --upgrade --component model
```

Adoption hashes the installed weights against the local pinned catalog and records only verified matches. It does not download replacement weights. Unknown/custom weights remain usable but require a separately reviewed model-selection procedure.

Routine updates keep the model ID, filename/quantization and explicit sampler settings. Downloaded weights must match the pinned revision, byte count and SHA-256. The updater checks GGUF and performs bounded generation with a managed llama CLI before and after activation. A failed check restores previous files. Keep sufficient RAM free; successful one-token generation does not establish performance or advice quality at your full context length.

Changing model family, size or quantization is a separate decision. Keep the old model and settings, select the candidate explicitly, compare the same saved evaluation prompts, and return to the old selection if results worsen. The updater does not silently switch to a larger model.

## llama.cpp, CUDA libraries and other managed runtimes

`--component llama` compares matching backend/platform releases. CUDA companion libraries are paired with their engine release and kept beside that engine. Runtime updates require publisher SHA-256 and exact size; unavailable checksums produce a manual status. The tool does not weaken verification automatically. Version and selected-model generation checks run before and after activation; a guide-only kit reports the model check as not run.

Llama archive links to files inside the archive are materialized as regular files. Existing internal library file links are backed up and restored with their original targets; directory links and escaping archive paths remain blocked. Each backend has a separate transaction. To undo a multi-backend upgrade, roll back its transactions in reverse application order.

Existing numbered llama.cpp installations (`bNNNNN`) follow that numbered build stream. GitHub marks these builds as prereleases; the report displays that fact. Drafts and unrelated experimental prerelease names are excluded.

`--component python` checks the installed Python minor version and platform. Apply it using a separate interpreter, for example `python3 emergency.py upgrade --component python` when `python3` is outside the kit. The updater refuses to replace the interpreter running the command. Legacy runtime trees containing unsupported links may need a manual, whole-directory swap with the old directory retained outside active runtime paths.

`--component kiwix-tools` compares the official platform listing. When the publisher does not provide trusted size/hash metadata, automatic installation is unavailable. For manual replacement: stop Kiwix, save its complete old runtime directory and version, verify the official artifact using available publisher integrity information, extract into a separate folder, run `kiwix-serve --version`, and test opening your existing ZIMs before swapping directories. Retain the old folder to reverse the swap.

`--component document-tools` uses the pinned tool catalog and preserves licenses. Existing document indexes require a reviewed extractor/index migration; the updater blocks replacement rather than invalidating those indexes silently. Foreign-platform binaries cannot be execution-tested on this host and are reported accordingly.

## Host drivers and operating system software

Drivers remain host-managed. The upgrade tool never runs sudo, package-manager commands, driver installers or reboots. Updating bundled CUDA libraries does not update the NVIDIA driver.

Before changing a host driver, record the GPU, driver version, OS/kernel and currently working llama backend; retain the previous installer/package and a working system backup. Check the candidate runtime's requirements against the vendor's supported driver/platform combinations. See [NVIDIA CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/latest/index.html).

- **Windows:** use Windows Update or the hardware vendor's supported installer. After restarting, test the same model/backend. If it fails, use Device Manager's **Roll Back Driver** when available, or reinstall the retained vendor version. [Microsoft driver update and rollback instructions](https://support.microsoft.com/en-gb/windows/update-drivers-through-device-manager-in-windows-ec62f46c-ff14-c91d-eead-d7126dc1f7b6).
- **Linux:** use the distribution's supported driver/package procedure. Keep the previous packages/kernel and the distribution's recovery instructions before upgrading; rollback commands differ by distribution. Test the GPU runtime after any required reboot, then restore the prior driver/kernel through that same package system if needed.
- **macOS:** manage system graphics software through supported macOS updates. Make a [Time Machine backup](https://support.apple.com/en-us/104984) before an OS change and retain Apple's recovery procedure. The app cannot undo an OS upgrade.

CPU mode can help diagnose a GPU regression, but is not proof that the GPU update succeeded.

## Kiwix data and indexes

```sh
./run.sh --adopt --component kiwix-data
./run.sh --upgrade --component kiwix-data
```

Adoption checks each archive against metadata for its **exact installed edition**, including size, SHA-256 and embedded ZIM checksum. If old metadata is no longer available, that archive stays unknown. Newer-edition metadata cannot authenticate an older file. Fixed historical snapshots are not automatically refreshed.

Updates match collection, language and variant. The verified replacement is installed transactionally and its matched predecessor is moved out of the served folder into the retained backup. Custom archives are untouched. Rollback restores the previous archive and provenance. For an externally managed Kiwix server, use that server's separate library activation procedure.

Automatic archive activation requires a managed Kiwix server for a bounded catalog and main-entry read before and after replacement. Edition-scoped source policies or existing document indexes require the staged migration below. These operational reads do not establish equivalent topic coverage across editions.

PDF/document collections with indexes require a manual staged migration: preserve the old ZIM, entire index directory, extractor and source-policy configuration; build a candidate index in a separate copy of the kit; check representative pages, citations, selection and reviewed precedence rules; then activate the archive/index/policies together with the app stopped. Keep the old set together for rollback. Ordinary archive upgrade does not claim to perform this migration.

## Verification after any change

Start the app, open local guides, verify the selected model and archive editions, and ask representative questions. Record the component identities with the results. Run the existing manual retrieval checks and saved emergency-advice replay when available. The durable versioned advice evaluation remains a separate work item; transaction journals explicitly record **advice_evaluation: not_run**.

Successful downloads, checksums, startup and one-token generation establish operational checks only. They do not establish that emergency answers improved. Keep the previous state until you have compared usefulness, withholding, source applicability, citations and action conditions.
