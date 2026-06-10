"""Runtime config for the Sway API."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


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
    root = Path(__file__).resolve().parents[3]
    for env_path in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env", root / ".env"):
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
            os.environ.setdefault(key.strip(), _dotenv_value(value))


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str | None
    api_public_url: str
    web_public_url: str
    google_credentials_encryption_key: str | None
    google_redirect_uri: str


def _normalize_public_url(url: str) -> str:
    cleaned = _dotenv_value(url)
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return cleaned.rstrip("/")


def get_settings() -> Settings:
    _load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not (url and key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required.")

    api_url = _normalize_public_url(os.environ.get("API_PUBLIC_URL", "http://localhost:8000"))
    web_url = _normalize_public_url(os.environ.get("WEB_PUBLIC_URL", "http://localhost:3000"))
    return Settings(
        supabase_url=_normalize_public_url(url),
        supabase_key=key,
        supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        api_public_url=api_url,
        web_public_url=web_url,
        google_credentials_encryption_key=os.environ.get("GOOGLE_CREDENTIALS_ENCRYPTION_KEY"),
        google_redirect_uri=os.environ.get(
            "GOOGLE_REDIRECT_URI",
            f"{api_url.rstrip('/')}/integrations/google/callback",
        ),
    )
