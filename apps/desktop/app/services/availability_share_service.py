"""Create public availability links through the Sway API."""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.cloud.config import load_api_public_url
from app.services.auth_service import AuthService


class AvailabilityShareError(Exception):
    """User-facing availability-share failure."""


@dataclass(frozen=True)
class AvailabilityShareResult:
    url: str
    expires_at: str


class AvailabilityShareService:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    @staticmethod
    def is_configured() -> bool:
        return load_api_public_url() is not None

    def is_available(self) -> bool:
        return self.is_configured() and self._auth.user is not None

    def create(self, snapshot: dict, creator_timezone: str) -> AvailabilityShareResult:
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
        except (URLError, OSError) as exc:
            raise AvailabilityShareError(
                f"Cannot reach the Sway API at {api_url}. Check API_PUBLIC_URL and ensure "
                "the API server is running."
            ) from exc
        except ValueError as exc:
            raise AvailabilityShareError("The server returned an invalid response.") from exc

        url = result.get("url")
        expires_at = result.get("expires_at")
        if (
            not isinstance(url, str)
            or not url
            or not isinstance(expires_at, str)
            or not expires_at
        ):
            raise AvailabilityShareError("The server returned an invalid share link.")
        return AvailabilityShareResult(url=url, expires_at=expires_at)


def _http_error_message(exc: HTTPError) -> str:
    try:
        detail = json.loads(exc.read()).get("detail")
    except (OSError, ValueError):
        detail = None
    return detail if isinstance(detail, str) and detail else "Unable to create share link."
