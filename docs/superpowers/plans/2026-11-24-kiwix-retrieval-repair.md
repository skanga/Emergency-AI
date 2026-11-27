# Retrieval and answer-quality follow-up

Status updated 2026-11-27. This replaces the stale implementation checklist; the original design and implementation history remain in Git. The user's release criterion is a reviewed improvement over main, with remaining limitations disclosed—not a perfect quality screen.

## Implemented and integrated

- Library identity, query planning, HTML extraction, source applicability, source conflict handling and context accounting.
- Offline PDF preparation with Xpdf, transactional document indexes and explicit unsupported/browse-only states.
- Browser and CLI retrieval diagnostics, library selection and source links.
- Versioned answer-quality evaluation with separate usefulness, unsafe-instruction, citation-error and withholding ratings. [Run instructions](../../../tests/evals/emergency_advice/README.md).
- Twenty-two source-backed fallback units in English, Portuguese and Spanish. Snakebite guidance includes urgent stretcher transport and breathing monitoring; the old “missing travel advice” item is superseded.
- Bounded action conditions and citation support, plus subsequent multilingual safety/grounding repairs. These are not general semantic entailment checks.
- Cross-platform upgrade, installation and rollback tests. The nine-job CI matrix passed on the proxy/extraction branch at `299c3c5`; this is engineering evidence, not native clinical evaluation.

[Repeated quality results](../../reviews/2026-11-26-answer-quality-results.md) retain the earlier 345 reviewed captures. [Fresh grounding findings](../../reviews/2026-11-26-grounding-live-evaluation.md) remain historical failing evidence; new checks must not rewrite their ratings. The original 59-case retrieval experiment had only 30 gold annotations and does not establish 90% recall or precision.

## Current corrective work

- [x] Reproduce Spanish coordinated-prohibition false positives and preserve affirmative/exception controls.
- [x] Require cited evidence for recognized limb elevation, preserving explicit conditions.
- [x] Check recognized cleaning instructions for region and organization attribution.
- [x] Detect the captured Crotalus efficacy reversal independently of other blocking claims.
- [x] Extend bounded causal matching with supported multilingual controls and unresolved-pronoun checks.
- [x] Replay the twenty historical drafts and all three isolated probes without editing their captures.
- [x] Exercise client-cold/warm, native-only, one/all libraries, unavailable Kiwix/model and blocked-external-network scenarios. This is a small operating smoke matrix, not an OS-cold or statistical performance benchmark.
- [x] Finish fresh multilingual and 32-case answer inspection, report all four quality dimensions, and retain failures. The 32-case screen fails; targeted corrections do not replace it.
- [x] Add source-backed dehydration escalation in EN/PT/ES after the fresh run exposed notice-only withholding. The catalog now contains 23 units; 22 were already integrated.
- [x] Complete final-code regression verification: 891 tests run, 20 skipped, no failures; four JavaScript checks pass. [Quality follow-up](../../reviews/2026-11-27-quality-followup.md).
- [ ] Complete branch integration. [Proxy evidence](../../reviews/2026-11-27-kiwix-proxy-validation.md) remains tied to its tested revision until merge is verified.

## Work requiring additional evidence

- Independently annotate the remaining retrieval cases and included-passage precision. The proposed 90% recall/precision targets have not been achieved or waived as measured results; they are not the user's incremental-merge criterion.
- Obtain clinician/first-aid and native-language review of the exact catalog hashes, then create independent holdout cases. The coding agent cannot supply that independence by relabeling its own review.
- Expand fallback coverage and known-condition checks when new failures establish a concrete need. Current regex matching cannot verify arbitrary explanations, all paraphrases, every regional protocol, or every action.
- Exercise physical phone/LAN use, native video playback and genuinely cold filesystem caches. Automated native CI and local Chromium proxy tests do not prove those scenarios.
- Update the standalone installation only through the documented upgrade procedure when authorized. This task does not replace its files or restart it.

Source mappings are maintained in [guidance references](../../references/guidance-sources.md) and [action-condition references](../../references/action-conditions.md). They are enduring provenance, not obsolete task records. Original local knowledge, archives and frozen evaluation evidence must be preserved.
