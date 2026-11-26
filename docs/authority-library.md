# Authority references

The first batch adds six **English editorial summaries**, available offline in guide search and AI retrieval. They are short, scoped summaries with source links, edition information and locators, not complete publisher manuals or certified translations. They are searchable from all three interface languages; their source language remains English.

| Source | Searchable coverage | Original for offline reading |
|---|---|---|
| IFRC 2025 first-aid guidelines | Scene safety and obtaining help | Verified optional PDF, 594 pages |
| WHO Community First Aid Response | SBAR handover communication only | Verified optional PDF, 12 pages; intended for trained community responders |
| CDC emergency water | Chemical-contamination exclusion, boiling, elevation and storage | Official PDF link; direct download blocked with HTTP 403 in this test environment |
| FEMA Are You Ready? (2020) | Evacuation/shelter planning and accessible transport | Verified optional PDF, 29 pages; historical U.S. guide, not current local alerts |
| FoodSafety.gov outage chart | Selected refrigerated-food rows with temperature/time conditions | Official web chart; direct download blocked with HTTP 403 in this test environment |
| WHO snakebite treatment | First aid, stillness and assisted transport | Official web source; mutable HTML, not a pinned binary download |

Sources and exact locators are in each summary and [the catalog](../config/authority-documents.json). All six summaries ship with the application in `knowledge/authorities/`. Your `knowledge/extra/` personal documents remain separate and protected by upgrades. Existing guides and Kiwix collections are retained. Authority names do not automatically override conflicting sources.

## Optional original PDFs

From the application folder, use its Python interpreter (or a compatible system Python):

```sh
python -m app.authority_documents --document ifrc-2025 --document who-cfar --document fema-ready
```

On systems where the command is `python3`, substitute `python3`. `--root /path/to/installation` selects the destination installation. Downloads go into `runtime/authorities/`; open those PDFs directly in your PDF reader. They are **not automatically indexed**. The command checks recorded sizes and SHA-256 hashes, reuses matching files, and retains publisher-rights notes. Hashes were observed from official HTTPS downloads; they are not publisher signatures. If upstream bytes change, verification fails; do not bypass it by deleting the recorded hash.

There is no download or extraction during startup or an emergency answer. The command uses the existing cross-platform downloader; PDF viewing does not require Xpdf. Extraction validation for this batch ran on Linux with Xpdf 4.06.

## Reuse and scope

The software license does not relicense original third-party publications. IFRC's original permits acknowledged noncommercial reproduction and requires permission for commercial reproduction. Document-specific redistribution permission for WHO CFAR has not been established here; obtain permission where required before redistributing originals. CDC has attribution, non-endorsement and third-party exceptions. Other federal sources also retain their applicable notices. The optional originals are not committed to Git or bundled in installation archives.

The full CFAR guide contains trained-responder procedures. Its searchable summary is restricted to handover communication, without instructions for those procedures. Full manuals require audience and procedure review before any future retrieval activation. Do not copy raw extraction into `knowledge/extra/` as a way around that boundary.

PDF layout checks rejected many pages in these documents. The shipped sections were reviewed against their cited source sections instead of accepting raw extraction as reliable. Adding an authoritative source does not prove that generated answers preserve its conditions. See the batch's answer-quality evidence and remaining limitations in `docs/reviews/2026-11-26-authority-first-batch.md`.
