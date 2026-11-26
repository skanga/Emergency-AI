# Answer-quality evaluation implementation plan

Goal: preserve and repeat the emergency-advice review with independent, auditable answer-quality assessments.
Architecture: a standalone stdlib runner, normalized run data, versioned rubrics, validated review annotations, and Markdown/JSON comparison reports, all under tests/.

1. Write tests in tests/test_advice_evaluation.py for partial SSE, missing done, grouped/omitted citations, refusal versus failure, stale reviews, comparison request mismatch, repeated live follow-up history, and ZIP/tar export exclusion. Run `python3 -B -m unittest tests.test_advice_evaluation -v`; confirm missing eval behavior fails.
2. Implement tests/evals/emergency_advice/{suite,runner,report}.py. Implement run/import/template/report/compare CLI commands. Retain failures and raw captures, forbid overwrites, validate all review bindings and rating domains. Rerun focused tests.
3. Import the 22 original cases and two historical captures. Add independent live follow-ups and boundary scenarios. Verify dated primary references; store scenario rubrics without copying articles. Mark baseline outcomes unreviewed until individually assessed.
4. Run against port 8090. Preserve request/answer/source/completion data and available provenance. Review each displayed answer against its rubric and supplied passages; distinguish mechanical citation validity from semantic support. Record uncertainty, especially hidden drafts.
5. Generate comparison reports. Verify no unsupported quality pass, no averaging away severe findings, and denominators include failures. Run the full unit suite and archive tests. Review the diff and document exact limitations and commands.

The user approved implementation; execute inline without a second plan approval. Keep unrelated untracked files and production data untouched. Do not merge or push as part of the eval task.

## Completed validation

All five steps are complete. The first run captured 32/32 cases, and evidence-based agent reviews cover all 32 current answers plus the 22-case historical release replay. The original baseline remains explicitly unreviewed under the new rubric. Results and limitations are in RESULTS.md.

Verification: 641 unit tests completed, 20 skipped, no failures; 24 eval-specific tests pass. ZIP/tar export exclusion, exact historical requests, live follow-up history, stale review/reference rejection, evidence validation, and report comparison are covered. A deliberately inverted rubric-hash guard caused test failures; restoring it returned the suite to green. JSON and local Markdown links validate.

An earlier sandbox run could not bind fixture servers. A subsequent run concurrent with model evaluation hit the existing 30 ms retrieval-budget test; that test and the final full suite passed after model generation completed. No production code was changed to accommodate it. Native Windows/macOS execution of this new suite is not yet verified locally; the existing nine-job CI matrix will run it on push.
