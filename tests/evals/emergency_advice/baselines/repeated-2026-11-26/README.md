# Repeated answer-quality evidence — 26 November 2026

All 345 captures across eight runs have exact bound agent reviews. The latest full-suite screen remains failed. Selected-case passes below are not whole-suite or clinical approval. [Interpretation and limits](../../../../../docs/reviews/2026-11-26-answer-quality-results.md).

| Run / commit | Manifest | Captures and reviews | Report | Provenance |
| --- | --- | --- | --- | --- |
| Baseline `aff2ec4` | `cases.json` | [96 captures](baseline.json), [reviews](baseline-reviews.json) | [Report](baseline-report.md), [summary](baseline-review-summary.md) | [Source/environment](advice-quality-baseline-provenance.json) |
| Initial candidate `0d2e1fa` | `cases.json` | [96 captures](candidate.json), [reviews](candidate-reviews.json) | [Calibrated report](candidate-calibrated-report.md), [summary](candidate-review-summary.md) | [Source/environment](advice-quality-candidate-provenance.json) |
| Refined `ecf0d23` | `cases.json` | [96 captures](refined.json), [reviews](refined-reviews.json) | [Report](refined-report.md), [summary](refined-review-summary.md) | [Source/environment](advice-quality-refined-provenance.json) |
| Action corrections `1bffd0a` | `cases.json` | [18 affected captures](final-affected.json), [reviews](final-affected-reviews.json) | [Report](final-affected-report.md), [summary](final-affected-review-summary.md) | [Source/environment](advice-quality-final-affected-provenance.json), [completion](final-capture-completion.json) |
| Development `1bffd0a` | `development-cases.json` | [12 captures](final-development.json), [reviews](final-development-reviews.json) | [Report](final-development-report.md), [summary](final-development-review-summary.md) | [Source/environment](advice-quality-final-development-provenance.json) |
| Routing targeted `dd0af0f` | `development-cases.json` | [9 captures](routing-targeted.json), [reviews](routing-targeted-reviews.json) | [Report](routing-targeted-report.md), [summary](routing-targeted-review-summary.md) | [Source/environment](advice-quality-routing-targeted-provenance.json), [completion](routing-capture-completion.json) |
| Routing full development `dd0af0f` | `development-cases.json` | [12 captures](routing-development.json), [reviews](routing-development-reviews.json) | [Report](routing-development-report.md), [summary](routing-development-review-summary.md) | [Source/environment](advice-quality-routing-development-provenance.json) |
| Burn corrections `0d458d5` | `development-cases.json` | [6 captures](burn-final.json), [reviews](burn-final-reviews.json) | [Report](burn-final-report.md), [summary](burn-final-review-summary.md) | [Source/environment](advice-quality-burn-final-provenance.json), [completion](burn-final-capture-completion.json) |

The manifests live two directories above this index. No original question or rubric was rewritten. Failed runs remain intact. Reviews bind exact request, answer, supplied source text, terminal state, rubric and reference manifest. The [verification summary](verification-summary.json) records all eight denominators and gates after independent binding validation. Raw events remain in the `/tmp/advice-quality-*` directories recorded in provenance; portable captures retain raw hashes and exact reviewable content.

Comparisons: [baseline → initial](initial-candidate-comparison.md), [baseline → refined](refined-full-comparison.md), [refined → affected18](refined-to-final-affected.md). Compact comparison JSON files omit duplicated answer pairs; regenerate the complete comparisons with the runner. Full-run and matched-request denominators differ where live conversation history changes.

Regenerate reports from the repository root into new output paths:

```sh
python3 tests/evals/emergency_advice/runner.py report \
  --run tests/evals/emergency_advice/baselines/repeated-2026-11-26/refined.json \
  --reviews tests/evals/emergency_advice/baselines/repeated-2026-11-26/refined-reviews.json \
  --output /tmp/reproduced-refined-report.md

python3 tests/evals/emergency_advice/runner.py \
  --manifest tests/evals/emergency_advice/development-cases.json report \
  --run tests/evals/emergency_advice/baselines/repeated-2026-11-26/burn-final.json \
  --reviews tests/evals/emergency_advice/baselines/repeated-2026-11-26/burn-final-reviews.json \
  --output /tmp/reproduced-burn-report.md
```

Report generation success is not a quality pass; inspect each report's gate. New captures need new reviews. These cases informed implementation and are not independent holdouts. Agent screening is not clinician or native-language certification. All files here are versioned in Git and excluded from installation archives by `tests/** export-ignore`.
