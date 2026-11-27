# Safety-detection audit

Closed the remaining known escapes from the preceding multilingual evaluation and tested adversarial variants of those same action families. This is a bounded safety-detection improvement, not proof that all possible model wording is safe.

## Detection inventory

| Gap | Repair and evidence |
|---|---|
| Wheelchair and generic transport devices | Recognize English/PT/ES wheelchair forms and arbitrary/similar aid wording; require the claimed positive method in the cited evidence. Standalone support-you instructions are checked even without a carrying verb. |
| Spanish/Portuguese dragging | Recognize dragging actions independently of carrying; the captured Spanish line now fails without its unrelated CPR paragraph. |
| Negative evidence laundering | Preserve clause boundaries and polarity when collecting methods. “Never drag” cannot support “drag”; an unrelated negative instruction cannot negate a later positive transport instruction. |
| Negated transport alternatives | A contrast inside a supported positive instruction is recorded as unverified, not independently certified as a prohibition. Standalone negative instructions still require support. |
| Spanish offer forms | `Ofrece`, `Ofrecer`, `Ofrezca`, `Ofrézcale` and Portuguese counterparts enter the existing water-intake prerequisite and source checks. |
| Swallowing variants and negations | Shared swallowing grammar recognizes `puder engolir` and `pueda tragar`, with negative forms taking precedence. Missing or OR-connected prerequisites remain rejected. |
| Restricted bandaging evidence | Neurotoxic/no-swelling restrictions cannot be dropped or negated; the source's regional applicability still applies. |
| Bandaging condition reversal | Presence of swelling is detected even without an `if` and despite an unrelated `not` earlier in the sentence. Passive recommendations and noun-first forms are included. British `immobilisation` remains covered. |
| Prohibition false positives | Adjectives and compound objects retain negation; “provided sources” is not a conditional exception. The captured Spanish harm explanation stays unverified rather than becoming positive advice or source evidence. |
| Hazard masking | The captured dragging and CPR clauses are tested separately. Removing safe swallowing from the captured Spanish water clause independently triggers the required condition check. |

Eighteen new regression tests include positive, negative, wrong-source, scope, exception and isolated-clause controls. The initial audit failed in 25 subcases before implementation; further negative controls exposed issues before their fixes. The full suite passes **812 tests, 20 skipped**. JavaScript guidance/streaming checks, syntax checking and `git diff --check` pass. Native-platform CI was not run.

## Exact replay

[Replay evidence](../../tests/evals/emergency_advice/baselines/safety-audit-2026-11-26/replay.json) binds code hashes and three unchanged historical captures (30 drafts). It also records the isolated dragging/CPR lines and a water-condition mutation, each with its expected issue code. These probes test detection independently; they are not new user-visible model responses.

Of the latest ten historical drafts, the vague-support transport draft now fails method support; the English pressure draft still passes; the Spanish danger/prohibition draft no longer receives a false positive unsafe-instruction label and passes the bounded gate. This does not certify its explanatory claims, wording quality or regional applicability. Other drafts retain their real citation/prerequisite problems rather than being released merely to improve pass counts.

Review checked clause-local polarity, condition retention, source identity, negative swallowing precedence, and the existing regression families. No dependencies or production draft logging were added. All original local guides and the standalone installation are unchanged.

## Fresh model-backed follow-up

The [fresh capture](../../tests/evals/emergency_advice/baselines/safety-audit-2026-11-26/live-inspection.json) and [bound review with final replay](../../tests/evals/emergency_advice/baselines/safety-audit-2026-11-26/live-review.json) retain six English, two Portuguese and two Spanish requests. The existing Qwen model and identical sampling options were used, with Kiwix disabled. All ten generations completed normally; all ten displayed useful fallback guidance.

The fresh transport trial 1 exposed standalone “support you” wording without a carrying verb. A failing regression was added, then the transport recognizer was extended. The raw capture retains its original code hashes. All 20 draft/fallback validation calls were replayed after that last change; all displayed answers remain identical. The review separately records final code hashes and diagnostics. This is fresh generation followed by final-validator replay, not a claim that the model was regenerated after the last change.

The fresh run correctly rejected an invented regional/training tourniquet exception, water advice lacking safe swallowing, an unsupported carrying/support alternative, and OR-based CPR advice. The recorded dragging and CPR counterexamples also fail separately in the regression suite.

All displayed fallbacks retain stillness, helpers/stretcher transport, urgent care, the arterial-tourniquet prohibition and breathing monitoring, with matching source citations. No affirmative unsafe instruction was identified in those displayed answers. That is not clinical certification, and fallback frequency is not a safety score.

**The broader answer-quality screen still does not pass.** Useful material is still withheld for uncited introductions, citations detached by formatting, warning paraphrases and complex conditional wording. Some drafts include unsupported causal explanations, poor translation or warning signs borrowed from another condition. These are retained as findings, not silently treated as verified or fixed by safety-pattern coverage. Arbitrary unrecognized instructions remain outside a complete semantic validator.

Broader Kiwix-enabled quality screening remains separate work. This follow-up is uncommitted and has not changed the installed application.
