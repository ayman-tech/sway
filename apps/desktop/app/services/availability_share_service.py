"""Create public availability links through the Sway API."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.cloud.config import load_api_public_url
from app.services.auth_service import AuthService


class AvailabilityShareError(Exception):
    """User-facing availability-share failure."""


class AvailabilityShareService:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    @staticmethod
    def is_configured() -> bool:
        return load_api_public_url() is not None

    def is_available(self) -> bool:
        return self.is_configured() and self._auth.user is not None

    def create(self, snapshot: dict, creator_timezone: str) -> str:
        api_url = load_api_public_url()
        token = self._auth.access_token
        if not api_url:
            raise AvailabilityShareError("API_PUBLIC_URL is not configured.")
        if not token:
            raise AvailabilityShareError("Sign in to create a share link.")

        request = Request(
            f"{api_url}/availability-shares",
            data=json.dumps({
                "snapshot": snapshot,
                "creator_timezone": creator_timezone,
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310 - configured API URL
                result = json.loads(response.read())
        except HTTPError as exc:
            raise AvailabilityShareError(_http_error_message(exc)) from exc
        except (URLError, OSError, ValueError) as exc:
            raise AvailabilityShareError("Unable to create share link. Check your connection.") from exc

        url = result.get("url")
        if not isinstance(url, str) or not url:
            raise AvailabilityShareError("The server returned an invalid share link.")
        return url


def _http_error_message(exc: HTTPError) -> str:
    try:
        detail = json.loads(exc.read()).get("detail")
    except (OSError, ValueError):
        detail = None
    return detail if isinstance(detail, str) and detail else "Unable to create share link."
