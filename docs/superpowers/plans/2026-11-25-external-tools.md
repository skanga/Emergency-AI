# External tool verification and upgrades

Scope: complete managed Kiwix/Xpdf provenance and update handling within the approved upgrade design. Drivers remain host-managed as specified; no package-manager or driver replacement.

- [x] Pin the reviewed official Linux x86_64 Kiwix 3.8.2 artifact in project metadata, explicitly identifying project SHA-256 provenance (publisher supplies only MD5). Reuse Xpdf's existing reviewed pin.
- [x] Test and implement byte-for-byte tool adoption, exact owned-file records, safe update discovery and changed-file refusal. Preserve indexes when adopting unchanged Xpdf; newer extractor activation remains blocked while indexes need migration.
- [x] Verify tool capabilities: open/read installed ZIMs with Kiwix and extract a synthetic PDF with Xpdf. Run these gates before and after tool activation.
- [x] Test provenance adoption/rollback/re-adoption on the real installation; tools are already at current reviewed versions, so do not invent an upgrade. Preserve archive/index/data hashes.
- [x] Independently review and run full regressions. Record source trust, current versions, tested recovery and explicit boundaries.
