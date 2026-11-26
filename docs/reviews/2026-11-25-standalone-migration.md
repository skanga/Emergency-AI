# Standalone migration completion

Historical migration-stage record. The upgrade implementation is now merged and the standalone app has subsequently been upgraded and rollback-tested at `d22579a`; see [the current release validation](2026-11-25-standalone-release-validation.md). Statements below about an older launcher and unmerged work describe the earlier migration stage.

Implemented a separate review/apply workflow for sparse or modified legacy standalone installations. The plan binds the target root, published commit, current manifest, source contents and permissions. Apply re-fetches the pinned source and recomputes the complete plan under the maintenance lock. A changed plan/install is refused. Existing configuration and knowledge remain locally owned; subsequent app upgrades exclude those preserved files. Other local paths are not adopted or deleted. Existing component provenance is retained.

The real `/home/skanga/Emergency` installation now has a verified app baseline at `ff7055b085851c6543adac2511d0259d2affe488`: 70 owned source files and 52 preserved configuration/knowledge files. Comparing against the published export found matching source bytes; archive mode normalization avoided unnecessary group-write permission changes. No source contents needed replacement in this installation. Sparse/mixed replacements and additions were exercised in fixtures.

Applied migration, tested UI/status/15 English guides/search through the installed launcher, executed the printed offline recovery command, verified full restoration, then reapplied migration and repeated startup checks. Final state is migrated and stopped, with no pending transactions. Across 9,621 tracked paths (excluding caches, logs and retained upgrade journals), rollback matched the original snapshot exactly; final migration changed only `runtime/installation.json`. Existing model/Kiwix/runtime component provenance is unchanged. Models and Kiwix were not launched for these UI checks.

- Tested rollback transaction: `46f6475b4cab4eeaa7b446382bfb4343`.
- Final committed transaction: `276368d61ff24727b086349c91a718c0`.
- Full suite: 582 tests, 16 skipped, zero failures/errors.
- Independent review: recovery-command target and malformed-input issues fixed; reviewer reran all nine migration tests and reported no outstanding findings.
- Mutation check: removing the plan equality guard caused the root/staleness regression test to fail; production code was not changed.
- Shell syntax and diff checks passed.

Existing configuration/catalogs and bundled knowledge excluded from ownership will not be refreshed by later app upgrades. Reconcile upstream revisions separately. Migration does not validate advice quality or full-context inference performance. The new updater remains in the separate worktree until committed/merged; the installed published launcher does not yet contain these new commands, so use the external updater for subsequent maintenance.

[Structured evidence](2026-11-25-standalone-migration-evidence.json). Detailed snapshots, plan, recovery and startup logs are in `/tmp/standalone-migration-test`. User procedure: [upgrades](../upgrades.md).
