"""Process-local Supabase clients backed by one bounded HTTP connection pool."""

from __future__ import annotations

from functools import lru_cache

import httpx
from fastapi import HTTPException, status
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from api.config import get_settings

CONNECT_TIMEOUT_SECONDS = 3.0
IO_TIMEOUT_SECONDS = 5.0
POOL_TIMEOUT_SECONDS = 2.0
MAX_CONNECTIONS = 20
MAX_KEEPALIVE_CONNECTIONS = 10
KEEPALIVE_EXPIRY_SECONDS = 60.0


@lru_cache(maxsize=1)
def shared_http_client() -> httpx.Client:
    """Return the connection pool owned by the current API worker process."""

    return httpx.Client(
        http2=True,
        timeout=httpx.Timeout(
            IO_TIMEOUT_SECONDS,
            connect=CONNECT_TIMEOUT_SECONDS,
            pool=POOL_TIMEOUT_SECONDS,
        ),
        limits=httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=KEEPALIVE_EXPIRY_SECONDS,
        ),
    )


def _client_options() -> SyncClientOptions:
    return SyncClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        postgrest_client_timeout=IO_TIMEOUT_SECONDS,
        httpx_client=shared_http_client(),
    )


@lru_cache(maxsize=1)
def authentication_client() -> Client:
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_key,
        options=_client_options(),
    )


@lru_cache(maxsize=1)
def admin_client() -> Client:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SUPABASE_SERVICE_ROLE_KEY is required for this operation.",
        )
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=_client_options(),
    )


def user_client(token: str) -> Client:
    """Create an isolated auth facade while reusing the worker's transport."""

    settings = get_settings()
    client = create_client(
        settings.supabase_url,
        settings.supabase_key,
        options=_client_options(),
    )
    client.postgrest.auth(token)
    return client


def initialize_supabase_clients() -> None:
    """Initialize immutable clients before a worker begins accepting traffic."""

    authentication_client()
    if get_settings().supabase_service_role_key:
        admin_client()


def close_supabase_clients() -> None:
    """Release cached facades and close the worker-owned connection pool."""

    authentication_client.cache_clear()
    admin_client.cache_clear()
    if shared_http_client.cache_info().currsize:
        shared_http_client().close()
    shared_http_client.cache_clear()
