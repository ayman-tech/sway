from __future__ import annotations

import json

import httpx
import pytest

from api.main import supabase_pool_timeout, supabase_timeout, supabase_transport_error


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

