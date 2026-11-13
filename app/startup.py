"""Inspect the local kit and offer setup without making startup depend on internet."""

import glob
import json
import os
import sys
import urllib.parse

from .config import CONFIG_DIR, MODELS_DIR, RUNTIME_DIR, ZIM_DIR, load_json, platform_key
from .kiwix import KiwixClient
from .launcher import find_kiwix_serve, find_llama_server, find_model
from .llm import detect_llm


def save_selection(selection, runtime_dir=None):
    directory = runtime_dir or RUNTIME_DIR
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "setup.json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(selection, f, indent=2)
    os.replace(path + ".tmp", path)


def load_selection(runtime_dir=None):
    directory = runtime_dir or RUNTIME_DIR
    saved = load_json(os.path.join(directory, "setup.json"))
    if saved is not None:
        if not isinstance(saved, dict) or any(not isinstance(saved.get(k), str)
                                               for k in ("model", "zims", "archives")):
            raise ValueError("Invalid saved setup choices; run 'start prepare' to choose again.")
        return saved
    # Preserve choices from kits prepared before unified startup was introduced.
    manifest = load_json(os.path.join(directory, "kit-info.json"), {}) or {}
    if not isinstance(manifest, dict) or "zim_profile" not in manifest:
        return None
    models = load_json(os.path.join(CONFIG_DIR, "models.json"), {}).get("models", [])
    filename = manifest.get("model")
    model = next((m["id"] for m in models if m["file"] == filename), filename or "none")
    return {"model": model, "zims": manifest["zim_profile"], "python": False,
            "archives": ",".join(a["id"] for a in manifest.get("archives", [])) or "none"}


def _present(path, size=None):
    try:
        actual = os.path.getsize(path)
        return os.path.isfile(path) and actual > 0 and (size is None or actual == size)
    except OSError:
        return False


def inspect(settings):
    """Cheap presence/size checks, not full hashes or release/update checks."""
    try:
        selection = load_selection()
        selection_error = None
    except (ValueError, TypeError, KeyError) as e:
        selection, selection_error = None, str(e)
    external_llm = detect_llm(settings) is not None
    kiwix_client = KiwixClient(settings.get("kiwix_url", "http://127.0.0.1:8092"))
    external_kiwix = bool(settings.get("kiwix_enabled", True) and kiwix_client.available())
    served = [b["name"] for b in kiwix_client.books()] if external_kiwix else []
    binary, _ = find_llama_server()
    kiwix = find_kiwix_serve()
    files = [p for p in glob.glob(os.path.join(ZIM_DIR, "**", "*.zim"), recursive=True) if _present(p)]
    missing = []
    if selection_error:
        state = "incomplete"
        missing.append(selection_error)
    elif selection is None:
        usable = external_llm or external_kiwix or (binary and find_model(settings)) or (kiwix and files)
        state = "available" if usable else "first_run"
    else:
        models = load_json(os.path.join(CONFIG_DIR, "models.json"), {}).get("models", [])
        libraries = load_json(os.path.join(CONFIG_DIR, "zims.json"), {})
        model_id = selection.get("model", "none")
        if model_id != "none" and settings.get("llm_backend", "auto") != "none" and not external_llm:
            model = next((m for m in models if m["id"] == model_id), None)
            if not model or not _present(os.path.join(MODELS_DIR, model["file"]), model.get("size_bytes")):
                missing.append("Model: " + str(model_id))
            if not binary:
                missing.append("AI engine for " + platform_key())
        profile = selection.get("zims", "none")
        archive_ids = str(selection.get("archives", "none"))
        if settings.get("kiwix_enabled", True) and (profile != "none" or archive_ids != "none"):
            if profile != "none" and profile not in libraries.get("profiles", {}):
                missing.append("Unknown library profile: " + str(profile))
            for entry in libraries.get("zims", []):
                if profile not in entry.get("profiles", []):
                    continue
                prefix = entry["name"] + ("_" + entry["variant"] if entry.get("variant") else "") + "_"
                if not (any(os.path.basename(p).startswith(prefix) for p in files)
                            or any(n == entry["name"] or n.startswith(prefix) for n in served)):
                    missing.append("Library: " + entry["name"])
            for archive_id in archive_ids.split(","):
                if archive_id == "none":
                    continue
                entry = next((a for a in libraries.get("archives", []) if a["id"] == archive_id), None)
                if not entry:
                    missing.append("Unknown archive: " + archive_id)
                else:
                    filename = os.path.basename(urllib.parse.urlsplit(entry["url"]).path)
                    if not (_present(os.path.join(ZIM_DIR, filename), entry["size_bytes"])
                            or filename[:-4] in served):
                        missing.append(f"Archive: {archive_id} ({entry['snapshot']})")
            if not kiwix and not external_kiwix:
                missing.append("Kiwix server for " + platform_key())
        state = "incomplete" if missing else "ready"
    return {"state": state, "missing": missing, "selection": selection,
            "external_llm": external_llm, "external_kiwix": external_kiwix}


def _select_model(settings, selection):
    if selection and "model_file" not in settings:
        models = load_json(os.path.join(CONFIG_DIR, "models.json"), {}).get("models", [])
        model = next((m for m in models if m["id"] == selection.get("model")), None)
        if model:
            settings["model_file"] = model["file"]


def ensure_ready(settings, lang="en", interactive=None):
    from . import prepare
    report = inspect(settings)
    _select_model(settings, report["selection"])
    if report["state"] in ("ready", "available"):
        return report
    if report["state"] == "first_run":
        print("First use: the included guides are available now, without downloads.")
        print("  1) Set up optional AI and libraries (internet required)")
        print("  2) Use guides now and remember this choice [default]")
    else:
        print("Some selected components are missing or incomplete on this computer:")
        for item in report["missing"]:
            print("  - " + item)
        print("  1) Resume setup for this computer (internet required)")
        print("  2) Continue with available components [default]")
    print("You can add or repair components later with 'start prepare' or 'start prepare --resume'.")
    if interactive is None:
        # Windows NUL can report isatty(); require a visible terminal too.
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        print("No interactive terminal; starting with available components.")
        return report
    while True:
        try:
            choice = input("Choose [2]: ").strip() or "2"
        except EOFError:
            return report
        if choice in ("1", "2"):
            break
    try:
        if choice == "2":
            if report["state"] == "first_run":
                save_selection({"model": "none", "zims": "none", "archives": "none", "python": False})
        elif report["state"] == "first_run" or report["selection"] is None:
            prepare.run(lang=lang)
        else:
            prepare.run(lang=lang, resume=True, oses="this", yes=True)
    except (OSError, ValueError, KeyboardInterrupt) as e:
        print(f"Setup did not finish: {e}")
    print("Starting with available components. Use 'start status' for details.")
    report = inspect(settings)
    _select_model(settings, report["selection"])
    return report
