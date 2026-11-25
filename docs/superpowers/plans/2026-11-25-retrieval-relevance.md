# Retrieval relevance follow-up

Authorized continuation of the Kiwix repair plan. Main is f218d9b; work is isolated on fix/retrieval-relevance. The merged branch was deleted locally/remotely; prepared indexes were retained.

## Diagnosed problems

- Literal trigger groups miss ordinary EN/PT/ES symptoms and explicit topic changes.
- Nonmedical requests collide with medical terms and unknown-topic fallback accepts one incidental word.
- Candidate and section scores favor lexical overlap and specialist subsections, not applicable complete first-aid guidance.
- Gold annotations name one particular section; those strict matches are not a complete relevance metric. Do not rewrite historical gold to inflate performance.

## Implementation and verification

1. Extend the existing deterministic vocabulary and intent handling, with tests for symptom paraphrases, negation, follow-ups, age and nonmedical collisions.
2. Repair topic/article/section applicability and ranking. Preserve local files, source conflicts, complete passages and request budgets. No external service, extra model or dependency.
3. Add a fresh frozen validation set before tuning. Treat the previous held-out set as observed regression data now. Measure intended topic recognition, negative-case abstention and inspected source applicability separately from historical exact-section recall.
4. Run full tests and actual native/PDF retrieval, inspect missed sections and final context, and document remaining limits. Do not claim clinical safety certification from retrieval tests.

This follows the previously approved architecture. Embedding infrastructure or a second model would add deployment dependencies; expanding phrases alone would leave ranking and intent defects unresolved. Fix all three layers rather than forcing citations.

## Completion record

Implemented and reviewed the planner, applicability, ranking and deduplication changes. Full suite: 423 tests, 16 skips, no failures; both Node suites pass. Historical targets 28/30; fresh topic checks24/24; 46 knowledge-file hashes unchanged. All five document collections prepared with explicit partial coverage. See [evaluation report](../../reviews/2026-11-25-relevance-followup.md) for evidence and remaining clinical-validation limits.
