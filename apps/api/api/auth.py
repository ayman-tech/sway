"""Supabase JWT auth helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, status
from starlette.concurrency import run_in_threadpool
from supabase import Client
from supabase_auth.errors import (
    AuthApiError,
    AuthError,
    AuthInvalidJwtError,
    AuthRetryableError,
)

from api.observability import log_upstream_failure, timed_stage
from api.supabase_clients import admin_client, authentication_client, user_client

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


def _lookup_api_key(token: str) -> CurrentUser:
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    client = admin_client()
    with timed_stage("supabase.api_key.lookup"):
        res = client.table("user_settings").select("user_id").eq("api_key_hash", key_hash).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired API key.")
    return CurrentUser(id=res.data[0]["user_id"], email=None, token=token, client=client, is_api_key=True)


def _auth_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.PoolTimeout):
        log_upstream_failure("auth_pool", exc)
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is busy.")
    if isinstance(exc, httpx.TimeoutException):
        log_upstream_failure("auth_timeout", exc)
        return HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "Authentication service timed out.")
    if isinstance(exc, httpx.TransportError):
        log_upstream_failure("auth_connection", exc)
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is unavailable.")
    if isinstance(exc, AuthRetryableError):
        log_upstream_failure("auth_service", exc)
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is unavailable.")
    if isinstance(exc, AuthInvalidJwtError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")
    if isinstance(exc, AuthApiError):
        if exc.status >= 500:
            log_upstream_failure("auth_service", exc)
            return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is unavailable.")
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")
    if isinstance(exc, AuthError):
        log_upstream_failure("auth_unknown", exc)
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is unavailable.")
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")


def _claims_from_response(response: object | None) -> Mapping[str, Any] | None:
    """Normalize the response shape returned by supported supabase-auth versions."""
    if response is None:
        return None
    if isinstance(response, Mapping):
        claims = response.get("claims")
    else:
        claims = getattr(response, "claims", None)
    return claims if isinstance(claims, Mapping) else None


def _resolve_current_user(authorization: str | None) -> CurrentUser:
    token = _bearer_token(authorization)
    if token.startswith(_API_KEY_PREFIX):
        return _lookup_api_key(token)
    try:
        with timed_stage("supabase.auth.get_claims"):
            response = authentication_client().auth.get_claims(token)
    except Exception as exc:
        raise _auth_failure(exc) from exc
    claims = _claims_from_response(response)
    user_id = claims.get("sub") if claims else None
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")
    return CurrentUser(
        id=user_id,
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
        token=token,
        client=user_client(token),
    )


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    # Starting this timer before scheduling the blocking work makes thread-pool
    # contention visible in production timing logs.
    with timed_stage("auth.resolve"):
        return await run_in_threadpool(_resolve_current_user, authorization)


UserDep = Depends(get_current_user)
