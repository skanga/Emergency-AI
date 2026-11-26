# Answer-quality follow-up design

Status: approved by the user on 2026-11-25 (local time). Builds on the approved paraphrase policy and the versioned answer-quality eval. No production behavior has changed as part of this design.

## Outcome and boundaries

Improve the advice actually displayed when generation fails validation, preserve consequential action conditions, and detect known cases where a real citation supports the wrong instruction. Complete repeated evaluation without weakening the existing rubrics to obtain a pass.

Keep paraphrased answers. Preserve original knowledge files, installed archives, model settings, and the standalone installation. Runtime behavior remains offline and standard-library-only. New evidence is an explicit, versioned addition, never a silent rewrite or an assertion that local storage is more authoritative than Kiwix.

## Alternatives

1. Recommended: source-backed fallback guidance plus bounded action and claim-support checks. This is inspectable, works without another model call, and addresses the captured failures. Coverage limits remain explicit.
2. Add a model verifier for every draft. This can recognize more wording but adds latency and can share the generator's mistakes. It is not an independent safety oracle; defer it.
3. Require source-exact procedures for all emergency answers. This constrains wording but reduces flexibility and may expose inappropriate source sections. It conflicts with the user's decision to retain paraphrases.

## Evidence and fallback guidance

Add a small production guidance catalog, separate from `knowledge/`, with stable IDs, authoritative reference URLs/titles, checked dates, source-supported paraphrases, scope, prerequisites, contraindications, language, and content hashes. Use short paraphrases rather than copying publisher pages. The catalog ships in installation archives; eval cases and results remain under excluded `tests/`.

Initial coverage follows the observed gaps: alert and unconscious hypoglycemia, responsive normally breathing people for whom CPR was proposed, severe bleeding when a layperson asks for IV treatment, unsuitable/unknown bleach and suspected chemical water contamination, burns, anaphylaxis, snakebite, flood entrapment, heat illness and cooking fires. Select by situation and explicit patient facts, never eval IDs or exact question strings. Include English, Portuguese and Spanish variants; language coverage must be tested rather than silently assumed.

Admit applicable guidance as identifiable evidence before prompt fitting, with ordinary displayed source numbers and readable provenance. Guidance can support normal generation as well as fallback. It must pass the same applicability and conflict policy. Its presence alone cannot establish precedence over contradictory evidence.

Fallback is deterministic composition of complete guidance units, not editing a rejected draft. Each unit preserves its conditions and citations. A unit must match explicit facts or retain explicit conditional wording. Assistant history cannot establish patient facts. Unknown location, species, product, dose or device must remain unknown. Do not invent emergency telephone numbers for an unknown location.

Use fallback after validation rejection, incomplete/failed generation or model unavailability. Keep deliberate search-only mode as evidence browsing. Preserve the rejection reason and record fallback selection separately. A fallback with no eligible guidance remains an honest limitation notice; do not manufacture an instruction. For unresolved conflicts, exclude the disputed actions and show only independently supported, applicable actions unaffected by the dispute. A policy-load failure cannot be bypassed by treating a catalog item as automatically trusted.

If a fallback cites evidence omitted from the model context, explicitly mark it as fallback evidence and include it in the displayed sources before its first citation. Do not imply that the rejected draft had access to it. Never stream rejected draft text or expose it in ordinary validation metadata.

## Action-condition checks

Extract recognized consequential actions and their attached conditions into bounded records rather than accumulating unrelated checks in the engine. Reuse patient-fact extraction and source applicability. Apply checks to both paraphrases and catalog fallback units.

Extend coverage to the observed defects: clothing removal with burns; airway protection during cooling/immersion; swallowing conditions for oral medication; regional/species restrictions on snake compression; device-specific injector timing; flood-vehicle conditions; and grease-fire equipment and safe-use conditions. Recheck primary references before encoding each rule. Do not use one jurisdiction's protocol as a universal rule.

Test affirmative, prohibited, conditional, quoted and hypothetical forms; conjunction versus disjunction; separate sentences and bullet lists; compatible user-history updates; negation; and matched valid counterparts. Avoid attaching a condition from an unrelated sentence to an instruction. Invalid consequential instructions reject the draft as a whole; fallback provides useful alternatives without rescuing unsupported fragments.

## Citation support

Keep exact ID, omitted-source and citation-link checks. Add claim records for recognized consequential instructions, including polarity, relevant quantities/units, device, patient scope and prerequisite conditions. A citation to a heading, disease definition or loosely related passage is insufficient.

Associate each recognized claim with the source IDs attached to its sentence or explicit procedure block. Require the cited passage itself to contain the matching action and necessary scope/conditions, or a versioned reviewed claim binding to that exact passage hash. Do not establish support from keywords anywhere in the whole retrieved set. Numbers must remain linked to the right action and unit. Changed source text invalidates reviewed bindings.

Reject recognized unsupported or contradictory consequential claims. Expose per-claim reason codes and evidence spans without the rejected draft. Retain an explicit `unverified` state for claims outside recognized coverage; never label a whole answer semantically verified because a bounded matcher passed. General explanations and unrecognized procedures still require independent answer-quality review. Do not silently relax these checks if they increase withholding; fix evidence coverage or provide supported fallback.

## Implementation sequence

1. Freeze captured failures and add valid counterparts and new boundary variants before changing production code.
2. Verify primary references and add the versioned evidence catalog with provenance, scope and language tests.
3. Implement fallback selection and integrate it into engine failure paths, preserving citation event order and conflict handling.
4. Add missing action-condition and claim-to-cited-passage checks, with rejection reasons and explicit coverage limits.
5. Run focused tests, mutation checks, full Python/JavaScript suites, and archive inclusion/exclusion checks. Use existing native CI coverage when pushed.
6. Run and review repeated live evaluations; fix observed regressions and repeat affected groups without overwriting or concealing failed runs.

## Repeated answer-quality evaluation

Use isolated app instances for the baseline `aff2ec4` and candidate code, with the same model, backend, knowledge and Kiwix configuration. Record actual launched paths/commits and configuration hashes; an operator-supplied root alone is insufficient. Reuse running model/Kiwix services only if their identity and settings can be recorded. Do not replace or restart the user's standalone app as an implicit deployment.

Run all 32 existing cases for three trials on each revision (96 answers per revision). Start fresh conversations per trial. Preserve historical follow-ups exactly and evaluate live conversations separately because their follow-up requests can differ. Capture and retain failures; no selective retries. Record latency and execution order; disclose stochastic variation rather than claiming causality.

Add boundary variants for each new rule, including permissible instructions and conflicting/absent evidence. Label these development cases, not an independent holdout. Keep old baselines and rubrics unchanged. Store compact reviewed results and provenance in Git, raw events in ignored output directories.

Read every displayed answer, cited passage and rubric before assigning the four existing dimensions: usefulness, unsafe instructions, citation errors, and withholding. Review bindings must cover exact captures. Report counts and denominators by case, trial and displayed answer type. A fallback is judged as the actual answer, not credited merely for replacing a notice. Hidden drafts remain unknown. Agent review is not clinician adjudication.

Completion of implementation and evaluation is separate from passing the quality screen. Report failures openly. The existing screen requires no major/critical safety or citation findings, usefulness at least 3, no unnecessary withholding, complete captures and complete non-uncertain reviews. Independent clinical review remains an external requirement before any claim of clinical approval.

## Reference checks started

Primary pages checked while preparing this design:

- [NHS burns](https://www.nhs.uk/conditions/burns-and-scalds/): clothing removal retains the exception for material stuck to the affected area.
- [CDC emergency water](https://www.cdc.gov/water-emergency/about/): chemical/fuel contamination is distinct from microbial disinfection; supports choosing a different safe source.
- [NHS hypoglycemia](https://www.nhs.uk/conditions/low-blood-sugar-hypoglycaemia/): conscious treatment and unconscious-patient restrictions are separate branches.
- [USFA cooking fire safety](https://www.usfa.fema.gov/prevention/home-fires/prevent-fires/cooking/): reference for the equipment and action review.

These checks establish design inputs, not approval of unimplemented guidance. Each production catalog entry needs its own exact claim-to-reference review and scope before activation.
