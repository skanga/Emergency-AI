# Guidance catalog sources and review status

This is an implementation evidence record, not clinician adjudication or medical certification. The catalog contains original short paraphrases with English, Portuguese and Spanish variants. The translations were checked during implementation for retained prerequisites, prohibitions, quantities and units; independent clinical and native-language review remains outstanding. The original reference checks were performed on 2026-11-26 UTC. Moving this record does not renew those checks. Runtime is offline.

## Source and scope decisions

| Stable unit | Primary reference | Section and scope decision |
| --- | --- | --- |
| `hypoglycemia-oral` | [CDC: Treatment of Low Blood Sugar](https://www.cdc.gov/diabetes/treatment/treatment-low-blood-sugar-hypoglycemia.html) | “The 15-15 rule”; adult-only conditional oral care, awake and safe swallowing. Child amounts require a separate plan and are not inferred. |
| `hypoglycemia-unresponsive` | [NHS: Low blood sugar](https://www.nhs.uk/conditions/low-blood-sugar-hypoglycaemia/) | “How to treat severe low blood sugar”; nonoral care, emergency help, available glucagon only with knowledge of use. Recovery positioning additionally retains normal breathing from the CPR reference below. |
| `cpr-boundary` | [St John Ambulance: How to do CPR](https://www.sja.org.uk/first-aid-advice/cpr/) | “CPR first aid”; responsive/normal-breathing boundary, adult arrest condition, dispatcher and AED help. This is not a complete CPR training procedure. |
| `bleeding-pressure` | [American Red Cross: Life-threatening external bleeding](https://www.redcross.org/take-a-class/resources/learn-first-aid/bleeding-life-threatening-external) | “How to stop bleeding”; direct pressure; the separate tourniquet unit carries limb/severity/device conditions. Training is ideal, not a mandatory prerequisite in the cited tourniquet article. No IV recipe is inferred from a request for invasive treatment. |
| `water-product` | [EPA: Emergency disinfection of drinking water](https://www.epa.gov/ground-water-and-drinking-water/emergency-disinfection-drinking-water) | Product restrictions; no dose when product or concentration is unknown. |
| `water-chemical` | [CDC: Emergency water](https://www.cdc.gov/water-emergency/about/) | “Water with fuel or toxic chemicals in it”; different safe supply, not microbial disinfection. |
| `burn-cooling` | [NHS: Burns and scalds](https://www.nhs.uk/conditions/burns-and-scalds/) | “What to do if you have a burn or scald”; thermal-burn condition and clothing-stuck exception retained. Chemical/electrical burn procedures are outside this unit. |
| `anaphylaxis-injector` | [NHS: Anaphylaxis](https://www.nhs.uk/conditions/anaphylaxis/) | “What to do if you have anaphylaxis”; device-specific directions remain on the device. Five minutes is the repeat-dose interval, not an injector hold time. |
| `snakebite-still` | [WHO: Snakebite envenoming](https://www.who.int/news-room/questions-and-answers/item/snakebite-envenoming) | “What is the appropriate first aid for snakebite?”; immobility and urgent transport. Compression varies by venom/tissue damage and region; unknown species/location cannot authorize it. |
| `flood-shelter` | [NWS: During a flood](https://www.weather.gov/safety/flood-during) and [NWS Pittsburgh: Floods](https://www.weather.gov/pbz/floods) | General safe elevation versus the specific moving-water vehicle condition. Roof refuge requires water rising inside the vehicle. |
| `heat-cooling` | [CDC NIOSH: Heat-related illnesses](https://www.cdc.gov/niosh/heat-stress/about/illnesses.html) | “Heat stroke: First aid”; cooling by wetting/fanning is selected. No unsupervised immersion procedure is included. |
| `cooking-fire` | [CPSC: Recipe for safer cooking](https://www.cpsc.gov/safety-education/safety-guides/home-fire/recipe-safer-cooking), [USFA: Cooking fire safety](https://www.usfa.fema.gov/prevention/home-fires/prevent-fires/cooking/), [USFA: Cook Safely flyer](https://www.usfa.fema.gov/downloads/fief/handouts/fief_cooking_safety_flyer_custom.pdf) | Small contained pan, safe approach and fitting lid prerequisites; no water or moving pan; leave/call from safety if unsafe or spreading. |

Emergency telephone numbers in national references are deliberately replaced with “emergency services” or local equivalent because the request may not establish a jurisdiction. The catalog does not silently assign a country or a device model.

## Integrity and integration contract

`app/data/guidance.json` has schema version 1. Each unit binds its ID, topic, scope, prerequisites, contraindications, reference metadata and all three translations with SHA-256 of UTF-8 canonical JSON (sorted keys, compact separators, no ASCII escaping), excluding only `content_hash`. Changing any of these requires an explicit new hash. This detects accidental alteration; it is not an external signature or an assertion of clinical authority. Reference checked dates are distinct from publisher review dates.

`guidance_sources(plan, lang)` returns unnumbered, applicable candidates. It uses existing planner topics/history and the shared applicability function. Each complete unit retains conditional instructions; a topic hint is not a patient diagnosis. Known contrary scope excludes the unit. Assistant history never adds patient facts. New aliases cover low blood sugar and cooking fires without interpreting a low-sugar recipe as an emergency.

`fallback_answer(sources, lang, conflicts)` accepts only complete canonical catalog sources with positive integer citation numbers. Altered text, IDs, hashes, language, URLs or provenance metadata are rejected. It composes whole units and inserts a citation at each sentence, without dropping any unit text or editing a rejected draft. The engine must admit the candidates and retain all canonical fields; merely adding `kind=guidance` to a retrieved passage is insufficient.

A policy-load error blocks all composition. Unknown or reviewed unresolved topic conflicts exclude all catalog units for that topic, including units whose source IDs were not directly named. Automatically detected water-treatment quantity conflicts can retain the canonical `safe_water_supply` action only; treatment units remain excluded, including boiling. A disputed source itself is always excluded. An unspecified unresolved topic blocks all composition. Reviewed precedence excludes nonpreferred bound IDs. These conservative rules may withhold an independently useful action because no action-level conflict resolution has been established.

Sources marked `context_omitted=True` (with canonical `original_text`) or `context_included=False` remain eligible for fallback, but their IDs appear in `fallback_evidence_ids`. The engine must add/mark these as fallback evidence in displayed sources **before** the first citation. The metadata never implies the rejected model draft saw those sources. Empty eligible evidence returns empty text and `status=unavailable`; the engine supplies its honest limitation notice. The engine must re-run its ordinary answer checks on composed output.

## Verification record

- Initial seven acceptance tests failed before implementation because no guidance module existed.
- A new flood-vehicle regression failed before the conditional vehicle branch was added.
- The shared applicability test exposed that “give nothing by mouth” was not recognized as a prohibition; the paraphrase was changed to an explicit “do not” form, retaining meaning and updating its content hash.
- `python3 -m unittest tests.test_guidance tests.test_query_planner -v` passed before the final shared-applicability addition (24 tests).
- `python3 -m unittest tests.test_guidance -v` passed after that addition (10 tests).
- All-unit own-citation validation smoke exposed English burn and multilingual flood condition matching gaps; these were reported to the root integration owner. The regression remains in the suite.
- Root integration, full suites, archive packaging, and repeated live evaluation are separate work; this record does not claim those results.

## Refinement after the frozen first candidate

The work below is isolated in `/tmp/emergency-ai-quality-refinement`, branched from frozen revision `0d2e1fa`. The earlier candidate worktree and its running evaluation were not edited. These additions address observed withholding and incomplete practical guidance; they do not change the fixed evaluation rubric.

New references checked on 2026-11-26 UTC:

| Unit | Primary and supporting references | Checked scope |
| --- | --- | --- |
| `adult-cpr-compressions` | [Red Cross adult CPR steps](https://www.redcross.org/take-a-class/cpr/performing-cpr/cpr-steps); [AHA 2025 adult BLS](https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/adult-basic-life-support), sections 7.1 and 7.3 | Adult arrest prerequisites, surface/hand placement, depth bounds, rate and recoil. |
| `adult-cpr-continuation` | [Red Cross adult cardiac arrest](https://www.redcross.org/take-a-class/resources/learn-first-aid/adult-cardiac-arrest), continuation FAQ; AHA adult BLS above | Trained/willing breathing option, compression fallback, AED prompts and stopping conditions. Arrival alone is not taking over. |
| `infant-choking-responsive` | [AHA/AAP 2025 pediatric BLS](https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/pediatric-basic-life-support), severe FBAO; [Red Cross infant choking](https://www.redcross.org/take-a-class/resources/learn-first-aid/infant-choking), general care | Responsive infant with severe obstruction; supported positioning, alternating maneuvers, stop/transition conditions and no blind sweeps. AHA is the primary clickable reference for its hand technique. |
| `infant-choking-unresponsive` | [Red Cross infant cardiac arrest](https://www.redcross.org/take-a-class/resources/learn-first-aid/infant-cardiac-arrest); AHA pediatric BLS above, sections 7.2–7.3; [NHS infant rescue breaths](https://www.nhs.uk/baby/first-aid-and-safety/first-aid/how-to-resuscitate-a-child/), rescue-breath technique only | Compression-first transition after choking, two-thumb technique, single-rescuer ratio, visible-object-only removal, neutral head and gentle breaths. No adult technique is admitted for a known infant. |
| `bleeding-tourniquet` | [Red Cross tourniquet application](https://www.redcross.org/take-a-class/resources/articles/how-to-apply-a-tourniquet); [USU Stop the Bleed](https://stopthebleed.usuhs.edu/index.html) | Uncontrolled life-threatening limb bleeding, available commercial device and training; placement, tightening and no loosening. No improvised-device procedure. |
| `stroke-response` | [CDC stroke signs](https://www.cdc.gov/stroke/signs-symptoms/index.html); [Red Cross stroke care](https://www.redcross.org/take-a-class/resources/learn-first-aid/stroke) | Immediate ambulance, onset/last-known-well information, no waiting for apparent recovery. |
| `poison-swallowed` | [Illinois Poison Center first aid](https://www.illinoispoisoncenter.org/health-safety/medications-and-first-aid/first-aid/); [National Capital Poison Center immediate assistance](https://www.poison.org/need-immediate-assistance) | Product-specific expert advice, no vomiting/neutralization, product information, emergency symptoms. Fluid guidance remains dependent on the product and swallowing/consciousness/seizure conditions; no blanket oral-fluid instruction. |
| `carbon-monoxide-escape` | [OSHA portable generator safety](https://www.osha.gov/sites/default/files/publications/OSHA3286.pdf); [CDC CO basics](https://www.cdc.gov/carbon-monoxide/about/index.html) | Immediate fresh air, emergency help, no garage ventilation exception and no unprotected re-entry. |
| `allergy-action-plan` | [FARE reaction symptoms](https://www.foodallergy.org/resources/recognizing-and-treating-reaction-symptoms); [FARE August 2025 care plan](https://www.foodallergy.org/sites/default/files/2025-08/ECP-FAAP_Plan_English_8_13_25.pdf) | Exposure without symptoms does not establish a diagnosis. Follow the individualized prescribed plan and monitor; medication triggers can differ by patient. |
| `food-outage` | [CDC emergency food safety](https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html); [FDA power-outage food safety](https://www.fda.gov/food/food-safety-during-emergencies/power-outages-key-tips-consumers-about-food-safety) | Perishable refrigerated food, cold-source/temperature exception, no tasting or smell-based assurance; shelf-stable alternatives. |

The bleeding-pressure unit now explicitly declines untrained IV insertion while retaining practical first aid. Its narrow training boundary is supported by the introduction of [UHBW NHS peripheral cannulation policy](https://www.uhbw.nhs.uk/assets/1/24-638_peripheral_venous_cannulae_policy_and_procedure_aug_23_redacted.pdf), page 6. This is an archived 2023 policy with an elapsed 2025 review date; only its general trained-practitioner requirement is used. No insertion, dosing or other clinical procedure is imported, and this record does not represent the archival document as a current treatment protocol.

### Source differences retained explicitly

AHA 2025 specifies heel-of-one-hand thrusts for severe infant choking; the public Red Cross choking page still describes two fingers. The catalog uses the AHA technique and links AHA first, with Red Cross supporting positioning and the general sequence. Two-thumb infant CPR is supported by AHA and Red Cross. The NHS generic infant CPR page differs in initial-breath sequence and finger technique; it supports only the neutral-head/mouth-and-nose rescue-breath mechanics here, not the selected compression-first choking transition. These differences are disclosed rather than silently asserted to agree. No precedence policy is inferred merely from catalog membership; conflicting admitted passages still use the ordinary conflict policy.

Independent review identified that the infant unit's single-rescuer prerequisite was present only in metadata. It is now explicit in every translation at the compression instruction and repetition. The primary choking reference was also changed after review so a user following its displayed citation reaches the source supporting the stated technique.

The original CPR boundary includes an adult procedure, so its source scope is now explicitly adult. This prevents an infant follow-up from mixing that source with the infant transition and being blocked by the existing source-age checks. Unknown-age adult instructions remain conditional; known child/infant/newborn cases do not receive the adult procedure units.

The chemical-water prohibition repeats its contamination scope in the operative sentence instead of relying on a preceding sentence's antecedent. Every anaphylaxis posture and repeat-dose instruction now states its own suspected-anaphylaxis condition. Shared patient facts do not yet model general absence of all allergy symptoms; the catalog therefore retains conditional guidance rather than inventing a parallel symptom classifier.

### Refinement verification

Tests were added before each behavior change. Initial refinement tests failed for absent actionable units and real-query validation failures. Additional RED regressions caught the infant follow-up mixing adult evidence, implicit single-rescuer ratio, absent outage/IV boundaries and unscoped anaphylaxis posture. All catalog translations are checked against their own citations using actual planner-triggering questions, and captured requests go through `Engine._fallback`, including history-based infant deterioration.

`python3 -m unittest tests.test_guidance -q` passed with 23 tests after these refinements. This includes all 22 units in all three languages and the actual-question runtime checks. The full suite and a new frozen repeated evaluation belong to the root integration task; success here does not establish the clinical correctness or independent safety approval of every answer.

### Pre-evaluation burn audit correction

A separate answer-rating audit identified missing loose covering, warmth and an explicit ice prohibition in the burn fallback. Before any refined-candidate answer request, the unused server was stopped and this unit was extended in all three languages. [NHS burns guidance](https://www.nhs.uk/conditions/burns-and-scalds/) supports cooling, stuck-clothing protection, loose film and escalation; [St John Ambulance's burn guidance](https://shop.sja.org.uk/blogs/workplace-first-aid/how-to-treat-burns-and-scalds) additionally supports keeping the rest of the person warm, avoiding ice, and excluding the face from film coverage. The supplied passage retains the no-circumferential-wrap condition. The original candidate's incomplete answers and their usefulness-2 ratings remain unchanged. A failing-first three-language regression and the complete catalog/fallback/claim tests passed (69 tests).

## Maintenance and review status

This is a maintained source-reference record, not a disposable completion report. The canonical references and content hashes remain in [guidance.json](../../app/data/guidance.json); the six separately curated authority summaries are recorded in [authority-documents.json](../../config/authority-documents.json). Keep historical evaluation captures unchanged when a reference changes.

The WHO snakebite first-aid section was reopened on 2026-11-27. It supports the catalog's stillness, urgent transport, tourniquet avoidance and qualified compression scope. This check does not validate archive statements about cleaning, limb elevation or species-specific tourniquet effectiveness. The new source-support regressions test fidelity to supplied passages, not permission to use those interventions.

Independent clinical review and native-language review are still required before describing the translations as independently approved. A reviewer should record the exact catalog content hash, unit, language, source section, decision and any correction. Engineering test success does not substitute for that review.

The Red Cross [tourniquet article](https://www.redcross.org/take-a-class/resources/articles/how-to-apply-a-tourniquet) was also reopened on 2026-11-27. Its training wording is an ideal, and it emphasizes that delaying care can be life-threatening. The catalog's explicit training prerequisite is a conservative editorial boundary, not a claim that this article prohibits every untrained rescuer from acting. Independent clinical review should adjudicate whether that boundary causes unnecessary withholding. Do not add a blanket validator prohibition on that basis alone.

### Dehydration escalation addition (2026-11-27)

| Stable unit | Primary reference | Section and scope decision |
| --- | --- | --- |
| `dehydration-escalation` | [NHS: Dehydration](https://www.nhs.uk/conditions/dehydration/), checked 2026-11-27; publisher review 2026-05-01 | Urgent-advice and immediate-action sections. Escalation only; no home ORS recipe, fluid administration, diagnosis, dosing or positioning procedure. |

The catalog now has 23 units. The added EN/PT/ES unit passes actual planner-to-fallback validation. It addresses the recorded notice-only dehydration failure; the original failed run remains unchanged. Independent clinical/native-language approval remains outstanding, as for the earlier units.

## November 27 actionable fallback corrections

The catalog now has 25 units. Three existing units changed (`bleeding-pressure`, `bleeding-tourniquet`, `snakebite-still`); two were added. Other original units and local knowledge files are unchanged. Hashes bind each revised unit and its source metadata.

- **Water conflict alternative:** `water-safe-supply` uses [CDC emergency water guidance](https://www.cdc.gov/water-emergency/about/) for a safe bottled supply and the chemical-contamination boundary. It contains no treatment dose or positive boiling instruction. Ambiguous numerical table fragments do not establish which treatment is correct. The exception is action-scoped and canonical-content checked, not an ID-based way around a conflict. Unknown conflicts, policy failures, and disputes involving the safe-supply source still block it.
- **Lone snakebite:** `snakebite-no-contact` combines [NPS signaling and injury guidance](https://www.nps.gov/articles/gtgemergencyplan.htm) with the [Red Cross necessary-walking exception](https://www.redcross.org/take-a-class/resources/learn-first-aid/venomous-snake-bites). It supplies signaling, asking a passerby to get rescue, and last-resort movement only when necessary and feasible on a known safe route. These are explicit editorial conditions, not a promise of safe self-evacuation. [AHA/Red Cross guidance](https://cpr.heart.org/en/resuscitation-science/2024-first-aid-guidelines/) discusses balancing exertion against delayed care **for North American indigenous snakes**; it does not authorize worldwide compression/washing protocols. The unit gives no walking-distance or waiting-time threshold. Independent clinical review remains outstanding.
- **Tourniquet applicability:** the [Red Cross tourniquet article](https://www.redcross.org/take-a-class/resources/articles/how-to-apply-a-tourniquet) describes trained responders as ideal and warns against delaying care. The catalog no longer makes training mandatory. It retains life-threatening arm/leg bleeding, a commercial device used according to its instructions, placement away from joints, tightening until bleeding stops, no loosening, and emergency help. It does not adopt the article's specialized torso remark. IV access remains restricted to trained practitioners. A generated instruction citing a different training-restricted passage must still retain that passage's restriction.

These pages were checked on 2026-11-27. EN/PT/ES wording was checked by the implementation agent; this is not independent clinician or native-language certification.
