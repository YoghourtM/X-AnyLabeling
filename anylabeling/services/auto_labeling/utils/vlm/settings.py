"""Persistent settings for the VLM annotator (one JSON file per user)."""

import copy
import json
import os

from anylabeling.config import get_work_directory

from .core import DEFAULT_MAX_VERTICES
from .providers import PROVIDER_CODEX, PROVIDERS

DEFAULT_SETTINGS = {
    "provider": PROVIDER_CODEX,
    "timeout": 600,
    "max_vertices": DEFAULT_MAX_VERTICES,
    "max_image_side": 2048,
    "instructions": "",
    # Batch runs: adaptive concurrency up to max_concurrency (see scheduler).
    "batch": {
        "max_concurrency": 4,
        "cooldown_seconds": 60,
        "max_retries": 3,
    },
    "codex": {
        "command": "codex",
        "model": "",
        "reasoning_effort": "medium",
    },
    "claude": {
        "command": "claude",
        "model": "",
    },
    "openai": {
        "base_url": "",
        "api_key": "",
        "model": "",
        "temperature": 0.0,
    },
}


def get_settings_path():
    return os.path.join(
        get_work_directory(),
        "xanylabeling_data",
        "vlm_annotator",
        "settings.json",
    )


def _merge(defaults, stored):
    merged = copy.deepcopy(defaults)
    for key, value in (stored or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge(merged[key], value)
        elif key in merged:
            merged[key] = value
    return merged


def load_settings(path=None):
    path = path or get_settings_path()
    stored = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as stream:
                stored = json.load(stream)
        except (OSError, json.JSONDecodeError):
            stored = {}
    settings = _merge(DEFAULT_SETTINGS, stored)
    if settings["provider"] not in PROVIDERS:
        settings["provider"] = DEFAULT_SETTINGS["provider"]
    return settings


def save_settings(settings, path=None):
    path = path or get_settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(settings, stream, ensure_ascii=False, indent=2)
    if os.name != "nt":
        os.chmod(temporary, 0o600)
    os.replace(temporary, path)
