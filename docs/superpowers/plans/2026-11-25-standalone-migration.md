# Standalone migration completion

Approved scope: complete the existing upgrade design's sparse/mixed standalone migration, preserving configuration and knowledge, previewing replacements, recording a verified baseline, and testing rollback.

Architecture: a separate migration module produces a root-bound, immutable-commit plan with before/after hashes and modes. Apply re-downloads the pinned source and recomputes the entire plan under the maintenance lock. Existing config/knowledge files are preserved and recorded as excluded ownership for subsequent app upgrades. Only candidate source paths are replaced/added; unrelated files are never deleted during migration. Transaction recovery remains the existing offline mechanism.

- [x] Add failing migration tests: sparse/modified source, preservation, stale/tampered plans, Git/owned-install rejection, failed health rollback and subsequent upgrades.
- [x] Implement plan/apply module and persistent preserved-file ownership handling.
- [x] Add launcher CLI preview/apply modes and tests; no provider discovery on apply beyond pinned source download.
- [x] Review and run targeted/full regressions.
- [x] Preview the real installation, validate the specific modifications, apply a pinned published commit, test startup and rollback, then verify preserved data and exact restoration.
- [x] Document commands, evidence and limits. Do not claim a commit means all preserved config/knowledge matches upstream.
