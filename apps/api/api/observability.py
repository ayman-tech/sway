"""Request-scoped timing logs for diagnosing slow external operations."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from time import perf_counter

_request_id: ContextVar[str] = ContextVar("sway_request_id", default="-")
logger = logging.getLogger("uvicorn.error")


def request_id() -> str:
    return _request_id.get()


def bind_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def log_upstream_failure(category: str, exc: Exception) -> None:
    """Log only a safe failure category and exception type."""

    logger.warning(
        "upstream_failure request_id=%s pid=%s category=%s error_type=%s",
        request_id(),
        os.getpid(),
        category,
        type(exc).__name__,
    )


@contextmanager
def timed_stage(stage: str) -> Iterator[None]:
    """Log the beginning and end of a safe, named request stage."""

    active_request_id = request_id()
    pid = os.getpid()
    started = perf_counter()
    logger.info(
        "timing stage_start request_id=%s pid=%s stage=%s",
        active_request_id,
        pid,
        stage,
    )
    try:
        yield
    except Exception as exc:
        duration_ms = (perf_counter() - started) * 1000
        logger.warning(
            "timing stage_error request_id=%s pid=%s stage=%s duration_ms=%.1f error_type=%s",
            active_request_id,
            pid,
            stage,
            duration_ms,
            type(exc).__name__,
        )
        raise
    else:
        duration_ms = (perf_counter() - started) * 1000
        logger.info(
            "timing stage_complete request_id=%s pid=%s stage=%s duration_ms=%.1f",
            active_request_id,
            pid,
            stage,
            duration_ms,
        )
