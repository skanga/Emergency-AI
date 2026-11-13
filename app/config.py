"""Paths, settings and platform detection."""

import json
import os
import platform
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")
WEB_DIR = os.path.join(ROOT, "web")
MODELS_DIR = os.path.join(ROOT, "models")
ZIM_DIR = os.path.join(ROOT, "zim")
RUNTIME_DIR = os.path.join(ROOT, "runtime")
LOG_DIR = os.path.join(ROOT, "logs")

LANGS = ("en", "pt", "es")

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOCAL_SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.local.json")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_settings():
    """settings.json + settings.local.json (local settings, ignored by git, take priority)."""
    settings = load_json(SETTINGS_FILE, {}) or {}
    local = load_json(LOCAL_SETTINGS_FILE, {}) or {}
    settings.update(local)
    return settings


def save_local_settings(changes):
    local = load_json(LOCAL_SETTINGS_FILE, {}) or {}
    local.update(changes)
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_DIR, delete=False) as f:
            path = f.name
            json.dump(local, f, indent=2, ensure_ascii=False)
        os.replace(path, LOCAL_SETTINGS_FILE)
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def platform_key():
    """Example: windows-x86_64, linux-arm64, macos-arm64."""
    system = platform.system().lower()
    if system.startswith("win"):
        osname = "windows"
    elif system == "darwin":
        osname = "macos"
    else:
        osname = "linux"
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64", "x64", "i686", "i386", "x86"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64", "armv8l", "armv8"):
        arch = "arm64"
    else:
        arch = machine
    return f"{osname}-{arch}"


ALL_PLATFORMS = (
    "windows-x86_64",
    "windows-arm64",
    "linux-x86_64",
    "linux-arm64",
    "macos-arm64",
    "macos-x86_64",
)


def is_windows():
    return sys.platform.startswith("win")


def exe(name):
    return name + ".exe" if is_windows() else name
