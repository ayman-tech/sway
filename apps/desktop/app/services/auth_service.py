"""Email/password auth against Supabase, with local session persistence."""

from __future__ import annotations

from dataclasses import dataclass

from supabase import Client, create_client

from app.cloud.config import is_configured, load_config
from app.repositories.settings_repo import SettingsRepository

_ACCESS_KEY = "sb_access_token"
_REFRESH_KEY = "sb_refresh_token"


class AuthError(Exception):
    """User-facing authentication failure."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None


class AuthService:
    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings = settings_repo
        self._client: Client | None = None
        self._user: AuthUser | None = None

    @property
    def client(self) -> Client | None:
        return self._client

    @property
    def user(self) -> AuthUser | None:
        return self._user

    @property
    def access_token(self) -> str | None:
        if self._client is not None:
            session = self._client.auth.get_session()
            if session is not None:
                return session.access_token
        return self._settings.get(_ACCESS_KEY) or None

    @staticmethod
    def is_configured() -> bool:
        return is_configured()

    def _ensure_client(self) -> Client:
        if self._client is None:
            cfg = load_config()
            if cfg is None:
                raise AuthError("Supabase isn’t configured yet.")
            self._client = create_client(cfg.url, cfg.anon_key)
        return self._client

    def sign_up(self, email: str, password: str) -> AuthUser:
        client = self._ensure_client()
        try:
            res = client.auth.sign_up({"email": email.strip(), "password": password})
        except Exception as exc:  # noqa: BLE001 (surface a clean message)
            raise AuthError(_clean(exc)) from exc
        if res.session is None:
            raise AuthError(
                "Account created, but email confirmation is on. Disable “Confirm email” "
                "in Supabase → Authentication → Providers, then sign in."
            )
        return self._apply_session(res.session)

    def sign_in(self, email: str, password: str) -> AuthUser:
        client = self._ensure_client()
        try:
            res = client.auth.sign_in_with_password(
                {"email": email.strip(), "password": password}
            )
        except Exception as exc:  # noqa: BLE001
            raise AuthError(_clean(exc)) from exc
        if res.session is None:
            raise AuthError("Sign-in failed. Check your email and password.")
        return self._apply_session(res.session)

    def restore_session(self) -> bool:
        """Try to resume a saved session on startup. Returns True if signed in."""
        if not is_configured():
            return False
        access = self._settings.get(_ACCESS_KEY)
        refresh = self._settings.get(_REFRESH_KEY)
        if not (access and refresh):
            return False
        try:
            client = self._ensure_client()
            res = client.auth.set_session(access, refresh)
            if res.session is None:
                return False
            self._apply_session(res.session)
            return True
        except Exception:  # noqa: BLE001 (expired/invalid → just show login)
            return False

    def sign_out(self) -> None:
        try:
            if self._client is not None:
                self._client.auth.sign_out()
        except Exception:  # noqa: BLE001
            pass
        self._user = None
        self._settings.set(_ACCESS_KEY, "")
        self._settings.set(_REFRESH_KEY, "")

    def _apply_session(self, session) -> AuthUser:
        client = self._ensure_client()
        # Ensure table requests carry the user's JWT (so RLS sees auth.uid()).
        client.postgrest.auth(session.access_token)
        self._settings.set(_ACCESS_KEY, session.access_token)
        self._settings.set(_REFRESH_KEY, session.refresh_token)
        self._user = AuthUser(id=session.user.id, email=session.user.email)
        return self._user


def _clean(exc: Exception) -> str:
    msg = str(exc).strip()
    return msg or "Authentication failed."
