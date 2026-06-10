"""Supabase connection config.

The project URL and anon (public) key identify *your* Supabase project. They are not
secrets — Row-Level Security is what protects data — so storing them locally is fine.

Resolved from, in order:
  1. environment variables SUPABASE_URL / SUPABASE_ANON_KEY
  2. a `.env` file in the working directory, desktop app root, or repo root
  3. a JSON file `supabase.json` in the app data dir:
     {"url": "...", "anon_key": "...", "api_url": "..."}
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.config import data_dir


def _normalize_url(url: str) -> str:
    """Reduce to the base project URL (drop a pasted /rest/v1 or other path)."""
    cleaned = _dotenv_value(url)
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return cleaned.rstrip("/")


def _dotenv_paths() -> list[Path]:
    desktop_root = Path(__file__).resolve().parents[2]
    repo_root = desktop_root.parents[1]
    paths = [Path.cwd() / ".env", desktop_root / ".env", repo_root / ".env"]
    return list(dict.fromkeys(paths))


def _dotenv_value(raw: str) -> str:
    """Parse a simple dotenv value while preserving hashes inside values."""
    value = raw.strip()
    if value[:1] in {"'", '"'}:
        quote = value[0]
        escaped = False
        for index, char in enumerate(value[1:], start=1):
            if char == quote and not escaped:
                return value[1:index]
            escaped = char == "\\" and not escaped
        return value[1:]
    return re.sub(r"\s+#.*$", "", value).rstrip()


def _load_dotenv() -> None:
    """Read local .env files into os.environ, without overriding existing values."""
    allowed = {
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_KEY",
        "API_PUBLIC_URL",
    }
    for env_path in _dotenv_paths():
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in allowed:
                os.environ.setdefault(key, _dotenv_value(value))


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    anon_key: str


def _config_path():
    return data_dir() / "supabase.json"


def load_config() -> SupabaseConfig | None:
    _load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    # The public client key: the new "publishable" key (sb_publishable_...) or the
    # legacy "anon" key both work here. Accept several names to avoid confusion.
    key = (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not (url and key):
        path = _config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                url = url or data.get("url")
                key = (
                    key
                    or data.get("publishable_key")
                    or data.get("anon_key")
                    or data.get("key")
                )
            except (OSError, ValueError):
                return None
    if url and key:
        return SupabaseConfig(url=_normalize_url(url), anon_key=key)
    return None


def is_configured() -> bool:
    return load_config() is not None


def load_api_public_url() -> str | None:
    """Return the FastAPI base URL used by authenticated desktop-only requests."""
    _load_dotenv()
    url = os.environ.get("API_PUBLIC_URL")
    if not url:
        path = _config_path()
        if path.exists():
            try:
                url = json.loads(path.read_text()).get("api_url")
            except (OSError, ValueError):
                return None
    return _normalize_url(url) if url else None
