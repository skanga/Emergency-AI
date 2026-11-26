# Guidance catalog reference check — 2026-11-26 UTC

This is an implementation evidence record, not clinician adjudication or medical certification. The catalog contains original short paraphrases with English, Portuguese and Spanish variants. The translations were checked during implementation for retained prerequisites, prohibitions, quantities and units; independent clinical and native-language review remains outstanding. Reference pages were opened or searched on the date above. Runtime is offline.

## Source and scope decisions

| Stable unit | Primary reference | Section and scope decision |
| --- | --- | --- |
| `hypoglycemia-oral` | [CDC: Treatment of Low Blood Sugar](https://www.cdc.gov/diabetes/treatment/treatment-low-blood-sugar-hypoglycemia.html) | “The 15-15 rule”; adult-only conditional oral care, awake and safe swallowing. Child amounts require a separate plan and are not inferred. |
| `hypoglycemia-unresponsive` | [NHS: Low blood sugar](https://www.nhs.uk/conditions/low-blood-sugar-hypoglycaemia/) | “How to treat severe low blood sugar”; nonoral care, emergency help, available glucagon only with knowledge of use. Recovery positioning additionally retains normal breathing from the CPR reference below. |
| `cpr-boundary` | [St John Ambulance: How to do CPR](https://www.sja.org.uk/first-aid-advice/cpr/) | “CPR first aid”; responsive/normal-breathing boundary, adult arrest condition, dispatcher and AED help. This is not a complete CPR training procedure. |
| `bleeding-pressure` | [American Red Cross: Life-threatening external bleeding](https://www.redcross.org/take-a-class/resources/learn-first-aid/bleeding-life-threatening-external) | “How to stop bleeding”; direct pressure and limb-only tourniquet with training. No IV recipe is inferred from a request for invasive treatment. |
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

A policy-load error blocks all composition. Unresolved topics exclude all catalog units for that topic, including units whose source IDs were not directly named in the conflict. An unspecified unresolved topic blocks all composition. Reviewed precedence excludes nonpreferred bound IDs. These conservative rules may withhold an independently useful action because no action-level conflict resolution has been established.

Sources marked `context_omitted=True` (with canonical `original_text`) or `context_included=False` remain eligible for fallback, but their IDs appear in `fallback_evidence_ids`. The engine must add/mark these as fallback evidence in displayed sources **before** the first citation. The metadata never implies the rejected model draft saw those sources. Empty eligible evidence returns empty text and `status=unavailable`; the engine supplies its honest limitation notice. The engine must re-run its ordinary answer checks on composed output.

## Verification record

- Initial seven acceptance tests failed before implementation because no guidance module existed.
- A new flood-vehicle regression failed before the conditional vehicle branch was added.
- The shared applicability test exposed that “give nothing by mouth” was not recognized as a prohibition; the paraphrase was changed to an explicit “do not” form, retaining meaning and updating its content hash.
- `python3 -m unittest tests.test_guidance tests.test_query_planner -v` passed before the final shared-applicability addition (24 tests).
- `python3 -m unittest tests.test_guidance -v` passed after that addition (10 tests).
- All-unit own-citation validation smoke exposed English burn and multilingual flood condition matching gaps; these were reported to the root integration owner. The regression remains in the suite.
- Root integration, full suites, archive packaging, and repeated live evaluation are separate work; this record does not claim those results.
