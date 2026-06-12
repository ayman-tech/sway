"""Supabase JWT auth helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, status
from supabase import Client, create_client

from api.config import get_settings

_API_KEY_PREFIX = "sway_"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    token: str
    client: Client
    is_api_key: bool = field(default=False)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    return authorization.split(" ", 1)[1].strip()


def user_client(token: str) -> Client:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(token)
    return client


def admin_client() -> Client:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SUPABASE_SERVICE_ROLE_KEY is required for this operation.",
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _lookup_api_key(token: str) -> CurrentUser:
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    client = admin_client()
    res = client.table("user_settings").select("user_id").eq("api_key_hash", key_hash).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired API key.")
    return CurrentUser(id=res.data[0]["user_id"], email=None, token=token, client=client, is_api_key=True)


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    token = _bearer_token(authorization)
    if token.startswith(_API_KEY_PREFIX):
        return _lookup_api_key(token)
    settings = get_settings()
    auth_client = create_client(settings.supabase_url, settings.supabase_key)
    try:
        res = auth_client.auth.get_user(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.") from exc
    if res.user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")
    return CurrentUser(
        id=res.user.id,
        email=res.user.email,
        token=token,
        client=user_client(token),
    )


UserDep = Depends(get_current_user)
