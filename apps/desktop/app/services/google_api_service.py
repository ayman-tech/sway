"""Desktop client for the centralized FastAPI Google Calendar integration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.cloud.config import load_api_public_url
from app.models.task import Task
from app.services.auth_service import AuthService
from sway_core.constants import TaskStatus


class GoogleApiError(Exception):
    """User-facing centralized Google integration failure."""


@dataclass(frozen=True)
class GoogleStatus:
    configured: bool
    connected: bool
    setup_available: bool
    client_id: str | None
    redirect_uri: str
    account: str | None
    last_synced_at: str | None
    last_sync_error: str | None


class GoogleApiService:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    def status(self) -> GoogleStatus:
        data = self._request("/integrations/google/status")
        return GoogleStatus(
            configured=bool(data.get("configured")),
            connected=bool(data.get("connected")),
            setup_available=bool(data.get("setup_available")),
            client_id=data.get("client_id"),
            redirect_uri=data.get("redirect_uri") or "",
            account=data.get("account"),
            last_synced_at=data.get("last_synced_at"),
            last_sync_error=data.get("last_sync_error"),
        )

    def save_credentials(self, client_id: str, client_secret: str) -> str:
        result = self._request(
            "/integrations/google/credentials",
            method="PUT",
            payload={"client_id": client_id, "client_secret": client_secret},
        )
        return _required_url(result)

    def connect_url(self) -> str:
        return _required_url(self._request("/integrations/google/connect-url"))

    def disconnect(self) -> None:
        self._request("/integrations/google", method="DELETE")

    def sync(self, force: bool = False) -> int:
        suffix = "?force=true" if force else ""
        result = self._request(f"/integrations/google/sync{suffix}", method="POST")
        return int(result.get("imported") or 0)

    def push_task_state(self, task: Task) -> None:
        self._request(
            f"/tasks/{task.id}",
            method="PATCH",
            payload={"reminder_minutes_before": task.reminder_minutes_before},
        )
        action = "complete" if task.status == TaskStatus.COMPLETED else "uncomplete"
        self._request(f"/tasks/{task.id}/{action}", method="POST")

    def _request(self, path: str, method: str = "GET", payload: dict | None = None) -> dict:
        api_url = load_api_public_url()
        token = self._auth.access_token
        if not api_url:
            raise GoogleApiError("API_PUBLIC_URL is not configured.")
        if not token:
            raise GoogleApiError("Sign in to use Google Calendar.")
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
            with urlopen(request, timeout=30) as response:  # noqa: S310 - configured API URL
                raw = response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raise GoogleApiError(_http_error_message(exc)) from exc
        except (URLError, OSError) as exc:
            raise GoogleApiError(f"Cannot reach the Sway API at {api_url}.") from exc
        except ValueError as exc:
            raise GoogleApiError("The server returned an invalid response.") from exc


def _required_url(data: dict) -> str:
    url = data.get("url")
    if not isinstance(url, str) or not url:
        raise GoogleApiError("The server returned an invalid Google authorization URL.")
    return url


def _http_error_message(exc: HTTPError) -> str:
    try:
        detail = json.loads(exc.read()).get("detail")
    except (OSError, ValueError):
        detail = None
    return detail if isinstance(detail, str) and detail else "Google Calendar request failed."
