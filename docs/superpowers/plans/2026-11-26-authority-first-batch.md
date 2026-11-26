# Authority first-batch implementation and verification

Approved scope: user requested testing and adding the six sources recommended in the preceding research. Execute inline extending the existing knowledge loader and download verifier; no new retrieval subsystem or dependencies.

Design: six English, explicitly labeled editorial summaries under knowledge/authorities, each a complete level-two section with source edition, audience, jurisdiction, locator and publisher link. These are searchable in EN/PT/ES as separately managed reference documents, but remain explicitly English, not publisher translations. Original guides and Kiwix files are unchanged. The full IFRC/WHO manuals are optional offline reading material outside knowledge; no clinical procedure activation from raw extraction. A manifest records official URLs, observed download hashes (not publisher signatures), terms and summary hashes. An explicit Python module downloads pinned PDF originals through app.prepare.download into runtime/authorities. Mutable HTML is linked with recorded audit hashes, not advertised as a stable downloadable artifact. No automatic online access at startup.

Alternative rejected: wholesale PDF ingestion would admit trained-responder instructions and uncertain table layouts. Links alone would not add offline searchable evidence.

- [x] Acquire the six original sources plus CDC scope page; record byte hashes and extraction page counts.
- [x] Inspect IFRC scene safety, WHO handover, CDC water, FEMA evacuation, food table headings and WHO snakebite transport in original layout.
- [x] Add failing tests for six manifest records, summary integrity, source locators, complete conditions, retrieval and download selection.
- [x] Add six summaries and manifest; add thin optional PDF-download module using existing verified download implementation.
- [x] Run retrieval and boundary tests; keep full trained-responder procedures outside the search index.
- [x] Run repeatable actual-answer probes against isolated app/model, review full answers and supplied citations, and preserve failures.
- [x] Run relevant/full regression checks and document extraction, reuse and answer-quality limits.

Acceptance: all six sources represented by useful offline sections and inspectable official references; PDF download integrity verified; summaries retain material conditions; original knowledge unchanged; no claims that added sources alone establish a whole-suite quality pass. Native execution tested locally on Linux; standard-library code and platform-independent paths intended for existing native CI.

Completed source addition and engineering checks. Live answer screening remains mixed; the full quality gate is not complete. See docs/reviews/2026-11-26-authority-first-batch.md for preserved failures and download limitations. No commit, push, merge or standalone deployment performed in this task.
