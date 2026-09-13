from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidJwtError,
    AuthRetryableError,
    AuthUnknownError,
)
from supabase_auth.types import ClaimsResponse

from api import auth


class FakeAuth:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.tokens: list[str] = []

    def get_claims(self, token: str):
        self.tokens.append(token)
        if self.error:
            raise self.error
        return self.result


def auth_client(fake_auth: FakeAuth):
    return SimpleNamespace(auth=fake_auth)


def test_resolves_user_from_verified_claims(monkeypatch) -> None:
    # supabase-auth's ClaimsResponse is a TypedDict at runtime, so production
    # returns a mapping rather than an object with a `.claims` attribute.
    verified = FakeAuth(
        ClaimsResponse(
            claims={"sub": "user-123", "email": "a@example.com"},
            header={},
            signature=b"",
        )
    )
    scoped_client = object()
    monkeypatch.setattr(auth, "authentication_client", lambda: auth_client(verified))
    monkeypatch.setattr(auth, "user_client", lambda token: scoped_client)

    user = auth._resolve_current_user("Bearer signed-token")

    assert user.id == "user-123"
    assert user.email == "a@example.com"
    assert user.token == "signed-token"
    assert user.client is scoped_client
    assert not user.is_api_key
    assert verified.tokens == ["signed-token"]


def test_resolves_legacy_object_claims_response(monkeypatch) -> None:
    verified = FakeAuth(SimpleNamespace(claims={"sub": "user-123"}))
    monkeypatch.setattr(auth, "authentication_client", lambda: auth_client(verified))
    monkeypatch.setattr(auth, "user_client", lambda token: object())

    assert auth._resolve_current_user("Bearer signed-token").id == "user-123"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AuthInvalidJwtError("private invalid detail"), 401),
        (AuthApiError("private invalid detail", 401, None), 401),
        (AuthApiError("private upstream detail", 500, None), 503),
        (AuthRetryableError("private upstream detail", 503), 503),
        (AuthUnknownError("private unknown detail", RuntimeError("nested detail")), 503),
        (httpx.ReadTimeout("private timeout detail"), 504),
        (httpx.ConnectError("private network detail"), 503),
        (httpx.PoolTimeout("private pool detail"), 503),
    ],
)
def test_auth_failures_are_classified_without_leaking_details(
    monkeypatch, error: Exception, expected_status: int
) -> None:
    monkeypatch.setattr(
        auth,
        "authentication_client",
        lambda: auth_client(FakeAuth(error=error)),
    )

    with pytest.raises(HTTPException) as caught:
        auth._resolve_current_user("Bearer signed-token")

    assert caught.value.status_code == expected_status
    assert "private" not in caught.value.detail


@pytest.mark.parametrize("claims", [None, {}, {"sub": ""}, {"sub": 123}])
def test_missing_verified_subject_is_unauthorized(monkeypatch, claims) -> None:
    result = None if claims is None else {"claims": claims}
    monkeypatch.setattr(
        auth,
        "authentication_client",
        lambda: auth_client(FakeAuth(result)),
    )

    with pytest.raises(HTTPException) as caught:
        auth._resolve_current_user("Bearer signed-token")

    assert caught.value.status_code == 401


def test_sway_api_key_path_is_unchanged(monkeypatch) -> None:
    expected = object()
    monkeypatch.setattr(auth, "_lookup_api_key", lambda token: expected)
    monkeypatch.setattr(
        auth,
        "authentication_client",
        lambda: pytest.fail("session authentication should not run for API keys"),
    )

    assert auth._resolve_current_user("Bearer sway_secret") is expected
