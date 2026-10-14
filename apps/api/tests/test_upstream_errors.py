from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from postgrest.exceptions import APIError, generate_default_error_message

import api.main as main
from api.main import supabase_gateway_error, supabase_pool_timeout, supabase_timeout, supabase_transport_error
from api.upstream_errors import retryable_gateway_status


def gateway_error(status_code: int = 400, body: str = "<html><h1>400 Bad Request</h1><center>cloudflare</center>private-secret</html>") -> APIError:
    # Construct exactly the wrapper produced by the installed PostgREST SDK.
    return APIError(generate_default_error_message(httpx.Response(status_code, content=body.encode())))


@pytest.mark.parametrize("status_code", [400, 502, 503, 504])
def test_known_non_json_gateway_response_classification(status_code):
    assert retryable_gateway_status(gateway_error(status_code)) == status_code


@pytest.mark.parametrize("code", [400, "400"])
def test_cloudflare_html_supports_numeric_and_string_status(code):
    error = APIError({"message": "JSON could not be generated", "code": code,
                      "details": "<!DOCTYPE html><html>CLOUDFLARE</html>"})
    assert retryable_gateway_status(error) == 400


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_gateway_failure_does_not_require_html(status_code):
    assert retryable_gateway_status(gateway_error(status_code, "")) == status_code


@pytest.mark.parametrize("error", [
    APIError({"code": "23505", "message": "duplicate key", "details": "private-secret"}),
    APIError({"code": "42501", "message": "permission denied"}),
    APIError({"code": "PGRST301", "message": "invalid JWT"}),
    APIError({"code": "400", "message": "bad filter", "details": "<html>cloudflare</html>"}),
    APIError({"code": "23505", "message": "JSON could not be generated", "details": "<html>cloudflare</html>"}),
    gateway_error(400, '{"message":"bad input"}'),
    gateway_error(400, "<html>ordinary bad request</html>"),
    gateway_error(400, "cloudflare"),
    gateway_error(401), gateway_error(403), gateway_error(404), gateway_error(429),
])
@pytest.mark.anyio
async def test_unmatched_errors_are_not_reclassified(error):
    assert retryable_gateway_status(error) is None
    with pytest.raises(APIError) as raised:
        await supabase_gateway_error(None, error)
    assert raised.value is error


@pytest.mark.anyio
async def test_task_gateway_failure_returns_sanitized_503_with_cors_and_timing(monkeypatch, caplog):
    calls = 0

    def fail_groups(*_args):
        nonlocal calls
        calls += 1
        raise gateway_error()

    monkeypatch.setattr(main, "groups_for", fail_groups)
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, lambda: SimpleNamespace(id="test-user"))
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            response = await client.get("/tasks/groups", headers={"Origin": "http://localhost:3010"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Data service is temporarily unavailable. Please try again."}
    assert response.headers["access-control-allow-origin"] == "http://localhost:3010"
    assert response.headers["x-request-id"]
    assert response.headers["server-timing"].startswith("app;dur=")
    assert calls == 1  # Never add another backend retry loop.
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "category=data_gateway_response" in messages
    assert "upstream_status=400" in messages
    assert f"request_id={response.headers['x-request-id']}" in messages
    assert "private-secret" not in messages + response.text
    assert "<html>" not in messages + response.text
    assert "request_error" not in messages
    assert not any(record.exc_info for record in caplog.records)


@pytest.mark.anyio
async def test_existing_auth_http_error_remains_401(monkeypatch):
    def unauthorized():
        raise HTTPException(401, "Invalid or expired token.")

    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, unauthorized)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/tasks/groups")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token."}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("handler", "error", "status_code", "detail"),
    [
        (supabase_pool_timeout, httpx.PoolTimeout("private"), 503, "Data service is busy."),
        (supabase_timeout, httpx.ReadTimeout("private"), 504, "Data service timed out."),
        (
            supabase_transport_error,
            httpx.ConnectError("private"),
            503,
            "Data service is unavailable.",
        ),
    ],
)
async def test_upstream_transport_errors_have_sanitized_retryable_responses(
    handler, error: Exception, status_code: int, detail: str
) -> None:
    response = await handler(None, error)

    assert response.status_code == status_code
    assert json.loads(response.body) == {"detail": detail}
    assert b"private" not in response.body

