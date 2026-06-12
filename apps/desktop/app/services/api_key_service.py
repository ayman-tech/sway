"""Desktop client for Sway API key management."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.cloud.config import load_api_public_url
from app.services.auth_service import AuthService


class ApiKeyError(Exception):
    """User-facing API key operation failure."""


class ApiKeyService:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    def get(self) -> dict:
        """Return {"key": str | None, "created_at": str | None}."""
        return self._request("/me/api-key")

    def generate(self) -> dict:
        """Generate (or replace) the API key. Returns the new key dict."""
        return self._request("/me/api-key", method="POST")

    def revoke(self) -> None:
        """Revoke the current API key."""
        self._request("/me/api-key", method="DELETE")

    def _request(self, path: str, method: str = "GET", payload: dict | None = None) -> dict:
        api_url = load_api_public_url()
        token = self._auth.access_token
        if not api_url:
            raise ApiKeyError("API_PUBLIC_URL is not configured.")
        if not token:
            raise ApiKeyError("Sign in to manage your API key.")
        request = Request(
            f"{api_url}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                raw = response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raise ApiKeyError(_http_error_message(exc)) from exc
        except (URLError, OSError) as exc:
            raise ApiKeyError(f"Cannot reach the Sway API at {api_url}.") from exc
        except ValueError as exc:
            raise ApiKeyError("The server returned an invalid response.") from exc


def _http_error_message(exc: HTTPError) -> str:
    try:
        detail = json.loads(exc.read()).get("detail")
    except (OSError, ValueError):
        detail = None
    return detail if isinstance(detail, str) and detail else "API key request failed."
