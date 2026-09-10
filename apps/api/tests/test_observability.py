from __future__ import annotations

import logging

import pytest
from api.observability import bind_request_id, reset_request_id, timed_stage


def test_timed_stage_logs_correlated_start_and_completion(caplog) -> None:
    token = bind_request_id("request-123")
    try:
        with (
            caplog.at_level(logging.INFO, logger="uvicorn.error"),
            timed_stage("supabase.tasks.select"),
        ):
            pass
    finally:
        reset_request_id(token)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "stage_start" in message and "request_id=request-123" in message
        for message in messages
    )
    assert any(
        "stage_complete" in message and "stage=supabase.tasks.select" in message
        for message in messages
    )


def test_timed_stage_logs_only_exception_type(caplog) -> None:
    token = bind_request_id("request-456")
    try:
        with (
            caplog.at_level(logging.INFO, logger="uvicorn.error"),
            pytest.raises(RuntimeError, match="private detail"),
            timed_stage("google.calendar.import"),
        ):
            raise RuntimeError("private detail")
    finally:
        reset_request_id(token)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "stage_error" in message and "error_type=RuntimeError" in message
        for message in messages
    )
    assert all("private detail" not in message for message in messages)
