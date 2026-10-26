"""A tiny JSON settings file: window position, opacity, always-on-top."""

from __future__ import annotations

import json
import os
from pathlib import Path


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "dashboard" / "settings.json"


def load_settings(path: Path | str | None = None) -> dict:
    """Read saved settings; a missing or damaged file means no settings."""
    target = Path(path) if path else config_path()
    try:
        data = json.loads(target.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict, path: Path | str | None = None) -> None:
    """Write settings atomically; a read-only home must never crash the widget."""
    target = Path(path) if path else config_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings))
        temporary.replace(target)
    except OSError:
        pass
