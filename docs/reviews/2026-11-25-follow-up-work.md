# Follow-up work from the emergency advice review

Recorded at the user's request on 25 November 2026. These are agreed follow-up needs, not completed capabilities. Current task: regression analysis of the generated advice.

## 1. Repeatable emergency-advice evaluation

Turn the saved 22 API cases and electrical-safety browser case into a versioned evaluation that can be run on demand against a chosen installation.

Acceptance goals:

- Preserve exact prompts, languages, initial/follow-up histories and baseline results in durable repository fixtures; `/tmp` must not be the permanent source of truth.
- Provide one documented command, with explicit target URL, output directory and baseline selection. Never overwrite historical runs.
- Evaluate retrieval and generated advice separately: relevant evidence included, source applicability, citations, conflict handling, critical required/forbidden actions, age/consciousness and follow-up continuity, response completeness and latency.
- Record app commit/build identity, settings, prompt version, model file/hash and sampler configuration, runtime versions, archive identities and index versions so comparisons can be attributed.
- Support deterministic checks and reviewed human judgments; do not equate keyword matches, an LLM judge, or source counts with clinical safety. Keep an independent holdout and versioned references/rubric.
- Produce case-level before/after artifacts and an aggregate regression report, including blocked answers and unsupported generation. Use repeats where generation variance matters.
- Make evaluation a validation step for each class of upgrade below.

Starting evidence: `docs/reviews/2026-11-25-emergency-advice-rerun.md`, `/tmp/emergency-advice-review/`, `/tmp/emergency-advice-rerun-2026-11-25/`, and existing `tests/manual` retrieval evaluations.

## 2. Proper upgrade procedures

Provide a documented, reviewable workflow for four independently versioned components:

| Component | Required scope |
|---|---|
| Application / Git repository | Git checkouts and separate non-Git installations; source/build identity, local changes, config migrations and defaults, staging, rollback, and post-upgrade verification. |
| Model | Model selection/version/hash, download verification, compatibility and memory checks, sampler/context settings, comparison against the current model, and rollback without deleting it. |
| External software | llama.cpp, Kiwix server, portable Python, extraction tools and relevant GPU libraries/drivers; distinguish application-managed runtimes from host-managed drivers, document platform compatibility and reboot/rollback requirements. |
| External data | Kiwix archive editions and other reference data; verified downloads, selection identity, index rebuild/invalidation, version-scoped source policies, added/removed coverage, and keeping previous data for rollback. |

Shared acceptance goals:

- Preserve local/personal knowledge, settings, reviewed precedence rules and downloaded assets; enumerate exactly what changes before applying an upgrade.
- Record a component inventory before and after; avoid silently changing several components together.
- Stage and verify replacements, keep a recoverable previous state, handle interrupted upgrades, and document storage requirements.
- Provide health checks plus the repeatable advice eval; report failures and make rollback practical.
- Never treat first-time setup as a substitute for an upgrade or automatically install host drivers as part of a routine app update.

Implementation/design work for these follow-ups remains pending. The user requested that regression analysis take priority now.
