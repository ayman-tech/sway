"""Sway MCP server — exposes Sway tasks to AI agents via the MCP protocol."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP

_API_URL = os.environ.get("SWAY_API_URL", "http://localhost:8010").rstrip("/")
_API_KEY = os.environ.get("SWAY_API_KEY", "")

mcp = FastMCP("Sway")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"}


@mcp.tool()
def list_tasks() -> list[dict[str, Any]]:
    """List all active (pending) tasks."""
    with httpx.Client() as client:
        res = client.get(f"{_API_URL}/tasks", headers=_headers())
        res.raise_for_status()
        return res.json()


@mcp.tool()
def get_task_groups(timezone_name: str = "UTC") -> list[dict[str, Any]]:
    """Get active tasks grouped into Overdue / Today / Next 7 days / Later.

    Args:
        timezone_name: IANA timezone, e.g. 'America/New_York'. Defaults to UTC.
    """
    with httpx.Client() as client:
        res = client.get(
            f"{_API_URL}/tasks/groups",
            params={"timezone_name": timezone_name},
            headers=_headers(),
        )
        res.raise_for_status()
        return res.json()


@mcp.tool()
def add_task(
    title: str,
    description: str | None = None,
    due_at: str | None = None,
    due_date: str | None = None,
) -> dict[str, Any]:
    """Create a new task.

    Args:
        title: Task title (required).
        description: Optional notes.
        due_at: ISO 8601 datetime with timezone for a timed task, e.g. '2026-06-15T14:00:00Z'.
        due_date: ISO 8601 date for an all-day task, e.g. '2026-06-15'. Mutually exclusive with due_at.
    """
    payload: dict[str, Any] = {"title": title}
    if description is not None:
        payload["description"] = description
    if due_at is not None:
        payload["due_at"] = due_at
    if due_date is not None:
        payload["due_date"] = due_date
    with httpx.Client() as client:
        res = client.post(f"{_API_URL}/tasks", json=payload, headers=_headers())
        res.raise_for_status()
        return res.json()


@mcp.tool()
def complete_task(task_id: str) -> dict[str, Any]:
    """Mark a task as complete.

    Args:
        task_id: The UUID of the task to complete.
    """
    with httpx.Client() as client:
        res = client.post(f"{_API_URL}/tasks/{task_id}/complete", headers=_headers())
        res.raise_for_status()
        return res.json()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
