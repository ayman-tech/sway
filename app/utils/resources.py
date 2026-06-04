"""Locate bundled resource files in both dev and a PyInstaller build."""

from __future__ import annotations

import sys
from pathlib import Path


def _base_dir() -> Path:
    # In a PyInstaller bundle, data files live under sys._MEIPASS; in dev they live
    # under the project root (this file is app/utils/resources.py → parents[2]).
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    """Path to a bundled resource, e.g. resource_path('app', 'db', 'schema.sql')."""
    return _base_dir().joinpath(*parts)
