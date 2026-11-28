# Content review TODO

Recorded: November 12, 2026. Status refreshed against main `105c294` on November 27, 2026.

This backlog covers the remaining nontechnical issues. The README glossary and archived-library date labels are already implemented. Unchecked items remain open; confirmed errors are distinguished from areas needing further review. The newer 25-unit fallback catalog does not replace or certify the original guides. Engineering/evaluation follow-ups are tracked separately in `docs/reviews/open-quality-work.md` (Git checkout only).

Apply relevant corrections consistently across the English, Portuguese and Spanish guides. The English file links below identify examples, not the full extent of the review.

## Priority 1: accuracy and safety

### Medical guidance

- [ ] Update the infant CPR instructions in [First aid and health care](knowledge/en/07-first-aid-medicine.md). They currently recommend two-finger compressions, which the 2025 AHA guidelines no longer recommend.
- [ ] Review the other medical sections against current guidance, including choking, bleeding, wound care, burns, dehydration, heat illness, allergic reactions and emergency childbirth.
- [ ] Clearly distinguish actions suitable for an untrained reader from procedures requiring training or professional care.
- [ ] Record the guideline edition and exact supporting source for each revised procedure; seek qualified clinical review and record whether it has occurred.

Reference: [2025 AHA Guidelines highlights](https://www.heart.org/en/-/media/CPR-Files/2025-documents-for-cpr-heart-edits-posting/Resuscitation-Science/252500_Hghlghts_2025ECCGuidelines.pdf).

### Food preservation

- [x] Correct questionable home-canned food advice in all three languages. The [English](knowledge/en/04-food.md), [Portuguese](knowledge/pt/04-food.md) and [Spanish](knowledge/es/04-food.md) guides now say to discard without tasting and not rely on boiling suspect food.
- [ ] Review meat drying, salting, smoking and storage under fat. Replace unsupported shortcuts and shelf-life claims with validated procedures and explicit temperature, equipment and storage limits.
- [ ] Review fermentation and mold advice, and link to tested preservation recipes rather than implying that a short summary is a complete process.

References: [CDC: Home-canned foods](https://www.cdc.gov/botulism/prevention/home-canned-foods.html), [National Center for Home Food Preservation](https://nchfp.uga.edu/).

### Water treatment

- [ ] Correct the [Water](knowledge/en/01-water.md) section that presents improvised distillation for chemically contaminated water without explaining its limits. Some volatile organic compounds, solvents and pesticides are not removed by distillation.
- [ ] Clearly separate treatment for microorganisms from treatment for chemical contamination; avoid implying that an improvised method makes an unknown water source safe.
- [ ] Verify disinfectant concentrations, measurement units, waiting times and regional product assumptions against the cited guidance.

Reference: [CDC: Home water treatment systems](https://www.cdc.gov/drinking-water/about/about-home-water-treatment-systems.html).

### Hazardous DIY procedures

- [ ] Remove the tongue-test instruction from [Homemade soap](knowledge/en/08-hygiene-sanitation.md). Review the improvised lye-strength tests and approximate mixing ratios before retaining a practical recipe.
- [ ] Obtain qualified review of the simplified distillation and fraction-selection instructions in [Alcohol](knowledge/en/09-alcohol.md). Do not imply that a fixed discard volume, smell or temperature establishes purity or safety.
- [ ] Review the connections between homemade alcohol, antiseptic production and instrument disinfection; distinguish their requirements and limitations.
- [ ] Replace procedures that cannot be adequately supported for a lay audience with safer alternatives or a clearly scoped explanation of the training and equipment required.

## Priority 2: sourcing and maintenance

- [ ] Replace generic organization homepages, vague book references and references to "traditional technique" with exact supporting pages, editions or sections.
- [ ] Check that each source actually supports the associated claim, quantity and procedure.
- [ ] Add review dates, source editions, regional scope and review status to the guides. Identify qualified reviewers where applicable; do not imply expert review when none has occurred.
- [ ] Define a maintenance process for updating guidance and propagating corrections across all 45 guides in the three languages.
- [ ] Keep source age separate from source reliability: an archive date label does not validate the contents of a downloaded library.

## Priority 2: localization and audience clarity

- [ ] Label Brazil-specific plants, medicines, climate assumptions, emergency services and regulatory advice explicitly; separate general guidance from regional examples.
- [ ] Review English text for leftover project branding and unexplained regional terminology, while preserving attribution and intentional multilingual content.
- [ ] Check translations for consistent quantities, units, warnings and procedure boundaries after each substantive correction.
- [ ] Separate basic emergency actions from advanced procedures requiring training, specialist equipment or supervision.
- [x] Remove the README claim that the app "answers any question". The three README introductions now describe reading guides, searching libraries and asking emergency questions. Ongoing coverage/limitation review remains part of the sourcing work.

## Completion checks

- [ ] Confirm that each identified unsafe or outdated passage has been corrected in every affected language.
- [ ] Verify links, calculations and units in the revised material.
- [ ] Read each revised procedure as a standalone passage, including its prerequisites, warnings, stopping conditions and sources.
- [ ] Record unresolved questions and any outstanding expert review explicitly before marking the corresponding item complete.
