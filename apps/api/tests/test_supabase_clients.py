from __future__ import annotations

from types import SimpleNamespace

import pytest

import api.supabase_clients as clients


@pytest.fixture(autouse=True)
def reset_clients():
    clients.close_supabase_clients()
    yield
    clients.close_supabase_clients()


def settings():
    return SimpleNamespace(
        supabase_url="https://example.supabase.co",
        supabase_key="publishable-key",
        supabase_service_role_key="service-role-key",
    )


def test_shared_transport_has_bounded_pool_and_timeouts(monkeypatch) -> None:
    captured: dict = {}

    class FakeHttpClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(clients.httpx, "Client", FakeHttpClient)

    first = clients.shared_http_client()
    second = clients.shared_http_client()

    assert first is second
    assert captured["http2"] is True
    assert captured["timeout"].connect == clients.CONNECT_TIMEOUT_SECONDS
    assert captured["timeout"].read == clients.IO_TIMEOUT_SECONDS
    assert captured["timeout"].write == clients.IO_TIMEOUT_SECONDS
    assert captured["timeout"].pool == clients.POOL_TIMEOUT_SECONDS
    assert captured["limits"].max_connections == clients.MAX_CONNECTIONS
    assert captured["limits"].max_keepalive_connections == clients.MAX_KEEPALIVE_CONNECTIONS
    assert captured["limits"].keepalive_expiry == clients.KEEPALIVE_EXPIRY_SECONDS


def test_user_clients_share_transport_but_not_authorization(monkeypatch) -> None:
    monkeypatch.setattr(clients, "get_settings", settings)

    first = clients.user_client("first-user-token")
    second = clients.user_client("second-user-token")

    assert first is not second
    assert first.postgrest.session is second.postgrest.session
    assert first.postgrest.headers is not second.postgrest.headers
    assert first.postgrest.headers["authorization"] == "Bearer first-user-token"
    assert second.postgrest.headers["authorization"] == "Bearer second-user-token"


def test_authentication_and_admin_clients_are_process_singletons(monkeypatch) -> None:
    monkeypatch.setattr(clients, "get_settings", settings)

    assert clients.authentication_client() is clients.authentication_client()
    assert clients.admin_client() is clients.admin_client()
    assert clients.authentication_client() is not clients.admin_client()
    assert clients.authentication_client().options.auto_refresh_token is False
    assert clients.authentication_client().options.persist_session is False


def test_startup_initializes_immutable_clients(monkeypatch) -> None:
    monkeypatch.setattr(clients, "get_settings", settings)

    clients.initialize_supabase_clients()

    assert clients.authentication_client.cache_info().currsize == 1
    assert clients.admin_client.cache_info().currsize == 1
    assert clients.shared_http_client.cache_info().currsize == 1


def test_shutdown_closes_and_replaces_the_worker_transport() -> None:
    first = clients.shared_http_client()

    clients.close_supabase_clients()

    assert first.is_closed
    second = clients.shared_http_client()
    assert second is not first
    assert not second.is_closed
