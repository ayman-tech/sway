"""Runtime configuration: file locations."""

from __future__ import annotations

import os
from pathlib import Path

from app.constants import APP_NAME


def data_dir() -> Path:
    """Per-user application data directory, created if missing.

    Honors SWAY_DATA_DIR for tests / portable runs.
    """
    override = os.environ.get("SWAY_DATA_DIR")
    if override:
        path = Path(override)
    else:
        # ~/Library/Application Support/Sway on macOS; ~/.local/share/Sway elsewhere.
        if os.name == "posix" and Path("~/Library/Application Support").expanduser().exists():
            base = Path("~/Library/Application Support").expanduser()
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
        path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "sway.db"
