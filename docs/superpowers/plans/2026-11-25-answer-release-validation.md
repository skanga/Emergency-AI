# Action conditions and citation validity

User choice: retain paraphrases, enforce known conditions, and disclose validation limits.

## Design

- Buffer generated prose until normal completion and validation. Never stream a rejected instruction or partial instruction before its condition has arrived. Keep existing retrieval/source events and done schema; add bounded validation diagnostics.
- Use application citation tokens `[S1]` in generation, distinct from original numeric footnotes. Validate every citation against sources actually included after token fitting. Reject numeric footnotes, unknown IDs, omitted IDs, malformed source tokens and citations without supplied evidence. Convert valid tokens to existing display numbers only after validation. Preserve original source text and IDs.
- Maintain a small deterministic action-condition policy for observed CPR prerequisites, oral treatment with impaired responsiveness/swallowing, and infant technique mismatches. Use current request and compatible user history, never assistant assertions, as patient facts. Unknown facts stay unknown; conditional instructions must retain their prerequisites. Block clinician-only procedures already excluded from retrieval if regenerated.
- Require application citations for recognized procedural instructions when evidence is supplied; membership does not establish entailment. No lexical similarity score will be presented as semantic verification.
- On validation rejection, display a localized withholding notice and reference links, not the rejected prose or an automatic rewritten procedure. Expose reason codes and checked limits without storing the rejected answer in metadata.
- Preserve ordinary non-emergency general-knowledge answers without fabricated citations. Search-only source display remains labeled original evidence, not validated paraphrases.

## Verification

RED tests cover namespace collision, original-text preservation, fitted/omitted citations, valid display remapping, split tokens, no premature output, incomplete/error streams, no-source citations, CPR loss of breathing condition, swallowing prerequisites, infant breathing technique, negation, language variants, follow-up facts and topic resets. Include valid counterparts to measure overblocking. Run full suite, Node suites, captured-answer checks and a small live generation smoke test. Fresh review and a mutation check precede completion.

## Limits

This is a pattern-based guard for known conditions, not a general medical parser, semantic entailment verifier, or clinical certification. Paraphrases outside recognized patterns may escape; valid complex wording may be withheld. Buffering adds time before answer text appears. No changes to knowledge, models, archives, installed service, deployment, or unrelated retrieval work.
