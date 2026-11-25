# Startup Language Filtering Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Startup must check only the libraries selected during setup, so a complete English-only installation starts without offering repair.

**Architecture:** Reuse `app.prepare.select_zims()` inside `app.startup.inspect()` instead of independently matching profile membership. Read the saved `zim_languages` and `include_english_references` fields using the same backward-compatible defaults as resume (`all` and `False`). Preserve archive checks, installed/externally served library detection, and the current llama.cpp upgrade behavior.

**Tech Stack:** Python standard library, unittest, unittest.mock.

## Scope and acceptance criteria

- A complete recommended English selection reports `ready` and does not prompt or call preparation.
- A missing selected English library still reports `incomplete`.
- Portuguese, Spanish, multiple languages, `all`, and optional English references use the same selection semantics as setup.
- Settings created before language filtering retain their all-language behavior.
- Invalid saved language/profile choices produce an actionable incomplete report rather than crashing startup.
- Archives remain independent of language filters, including when the regular profile is `none`.
- No downloads are needed for verification. No changes to engine version selection, upgrade behavior, or WSL networking.

## Task 1: Reproduce the startup mismatch

**Modify:** `tests/test_startup.py` (`StartupTests`).

- [x] Add this regression test using the existing temporary directories and service mocks:

```python
def test_complete_english_selection_starts_without_setup(self):
    cfg = prepare.load_json(str(Path(prepare.CONFIG_DIR) / "zims.json"))
    self.save(zims="recommended", zim_languages="en",
              include_english_references=False)
    self.kiwix.return_value = "kiwix-serve"
    entries = prepare.select_zims(cfg, "recommended", "en", False)
    for entry in entries:
        prefix = entry["name"] + ("_" + entry["variant"] if entry.get("variant") else "")
        (self.root / "zim" / (prefix + "_2026-01.zim")).write_bytes(b"library")
    with patch("builtins.input", return_value="2") as ask, patch.object(prepare, "run") as setup:
        report = self.startup.ensure_ready(self.settings, interactive=True)
    self.assertEqual(report["missing"], [])
    self.assertEqual(report["state"], "ready")
    ask.assert_not_called()
    setup.assert_not_called()
    (self.root / "zim" / "zimgit-water_en_2026-01.zim").unlink()
    report = self.startup.inspect(self.settings)
    self.assertEqual(report["state"], "incomplete")
    self.assertEqual(report["missing"], ["Library: zimgit-water_en"])
```

- [x] Run `python3 -m unittest discover -s tests -p test_startup.py -v`.
  Expected: the new regression fails because startup requires Portuguese and Spanish medicine libraries. Confirm that failure before editing production code.

## Task 2: Share the selection logic

**Modify:** `app/startup.py`, inside `inspect()` around the profile validation and regular-library loop.

- [x] Replace the current profile-only selection and loop header with:

```python
            from .prepare import select_zims

            selected_libraries = []
            if profile != "none":
                if profile not in libraries.get("profiles", {}):
                    missing.append("Unknown library profile: " + str(profile))
                else:
                    try:
                        selected_libraries = select_zims(
                            libraries, profile,
                            selection.get("zim_languages", "all"),
                            selection.get("include_english_references", False),
                        )
                    except (ValueError, TypeError, AttributeError) as exc:
                        missing.append("Invalid saved library selection: " + str(exc))
            for entry in selected_libraries:
```

  Keep the existing prefix construction, local-file checks, external-server checks, archive loop, and Kiwix executable check after this header. Remove the old profile-membership `continue`. The local import follows the existing startup-to-prepare pattern and invokes only a pure selection helper; it does not run setup or query releases.

- [x] Re-run `python3 -m unittest discover -s tests -p test_startup.py -v`.
  Expected: the regression and existing startup tests pass.

## Task 3: Cover compatibility and selection boundaries

**Modify:** `tests/test_startup.py` (`StartupTests`).

- [x] Add the following tests. Existing `tests/test_zim_languages.py` already independently checks the selector's language/reference semantics; the matrix below checks that startup applies them.

```python
def test_startup_checks_saved_language_selection(self):
    cfg = prepare.load_json(str(Path(prepare.CONFIG_DIR) / "zims.json"))
    self.kiwix.return_value = "kiwix-serve"
    cases = [({}, "all", False)]
    cases += [
        ({"zim_languages": languages, "include_english_references": refs}, languages, refs)
        for languages, refs in [("en", False), ("pt", False), ("es", False),
                                ("pt,es", False), ("all", False), ("pt", True)]
    ]
    for saved, languages, refs in cases:
        with self.subTest(saved=saved):
            self.save(zims="full", **saved)
            expected = {"Library: " + entry["name"] for entry in
                        prepare.select_zims(cfg, "full", languages, refs)}
            report = self.startup.inspect(self.settings)
            self.assertEqual(set(report["missing"]), expected)
            self.assertEqual(report["state"], "incomplete")

def test_invalid_saved_library_filter_is_reported(self):
    self.kiwix.return_value = "kiwix-serve"
    for languages in ("xx", "", "all,pt", None, ["en"]):
        with self.subTest(languages=languages):
            self.save(zims="recommended", zim_languages=languages)
            report = self.startup.inspect(self.settings)
            self.assertEqual(report["state"], "incomplete")
            self.assertTrue(any(item.startswith("Invalid saved library selection:")
                                for item in report["missing"]))
    self.save(zims="unknown", zim_languages="en")
    self.assertIn("Unknown library profile: unknown",
                  self.startup.inspect(self.settings)["missing"])

def test_archive_checks_are_independent_of_language_selection(self):
    self.kiwix.return_value = "kiwix-serve"
    self.save(zims="none", zim_languages="pt", archives="wikem")
    report = self.startup.inspect(self.settings)
    self.assertEqual(report["missing"], ["Archive: wikem (2020-06)"])
    self.save(zims="none", zim_languages="pt", archives="none")
    self.assertEqual(self.startup.inspect(self.settings)["state"], "ready")

def test_external_libraries_honor_saved_language_selection(self):
    cfg = prepare.load_json(str(Path(prepare.CONFIG_DIR) / "zims.json"))
    self.save(zims="recommended", zim_languages="en")
    books = [{"name": entry["name"]} for entry in
             prepare.select_zims(cfg, "recommended", "en", False)]
    with patch.object(self.startup.KiwixClient, "available", return_value=True), \
            patch.object(self.startup.KiwixClient, "books", return_value=books):
        report = self.startup.inspect(self.settings)
    self.assertEqual(report["missing"], [])
    self.assertEqual(report["state"], "ready")
```

- [x] Run the focused tests:

```sh
python3 -m unittest discover -s tests -p test_startup.py -v
python3 -m unittest discover -s tests -p test_zim_languages.py -v
python3 -m unittest discover -s tests -p test_prepare.py -v
```

  Expected: all pass; setup/resume and release-selection behavior remain unchanged.

## Task 4: Verify and review

- [x] Run `python3 -m unittest discover -s tests -v` and investigate failures before claiming completion.
- [x] Run `git diff --check` and review the diff. Production changes should be confined to startup library selection; no engine upgrade, downloader, archive, or WSL behavior changes.
- [x] Review using the code-review-and-quality skill. Report the regression result, full-suite outcome, and any remaining limitations. Do not claim a full WSL reinstall was tested: these tests reproduce the selection mismatch locally without large downloads.

**Expected user-visible result:** A kit prepared with recommended English libraries plus WikEM starts directly once those selected components are installed. Choosing resume explicitly still checks for and installs newer llama.cpp releases.

## Implementation verification

Implemented in `app/startup.py` with five regression tests in `tests/test_startup.py`. The original code reproduced the exact Portuguese/Spanish false warnings. All 35 focused tests passed after the fix. The full suite passed with socket access: 289 tests run, 16 skipped. A mutation disabling English references was caught by the regression suite; the restored code passed all 20 startup tests. `git diff --check` passed. Review found no blocking issues. A fresh WSL installation with real downloads was not rerun.
