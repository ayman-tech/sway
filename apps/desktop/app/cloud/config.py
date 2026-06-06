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
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.config import data_dir


def _normalize_url(url: str) -> str:
    """Reduce to the base project URL (drop a pasted /rest/v1 or other path)."""
    parsed = urlparse(url.strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url.strip().rstrip("/")


def _dotenv_paths() -> list[Path]:
    desktop_root = Path(__file__).resolve().parents[2]
    repo_root = desktop_root.parents[1]
    paths = [Path.cwd() / ".env", desktop_root / ".env", repo_root / ".env"]
    return list(dict.fromkeys(paths))


def _load_dotenv() -> None:
    """Read local .env files into os.environ, without overriding existing values."""
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
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    anon_key: str


@dataclass(frozen=True)
class GoogleConfig:
    client_id: str
    client_secret: str


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
    return url.strip().rstrip("/") if url else None


def load_google_config() -> GoogleConfig | None:
    """OAuth client credentials for the Google Calendar import (a Desktop app client)."""
    _load_dotenv()
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (client_id and client_secret):
        path = data_dir() / "google.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                # Accept either a flat file or Google's downloaded {"installed": {...}}.
                inner = data.get("installed") or data.get("web") or data
                client_id = client_id or inner.get("client_id")
                client_secret = client_secret or inner.get("client_secret")
            except (OSError, ValueError):
                return None
    if client_id and client_secret:
        return GoogleConfig(client_id=client_id, client_secret=client_secret)
    return None


def is_google_configured() -> bool:
    return load_google_config() is not None


def save_google_config(client_id: str, client_secret: str) -> None:
    """Persist OAuth client credentials locally (so no .env editing is needed)."""
    path = data_dir() / "google.json"
    path.write_text(
        json.dumps({"client_id": client_id.strip(), "client_secret": client_secret.strip()})
    )
