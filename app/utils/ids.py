"""UUID string ID generation."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Return a new random UUID4 string, used as a local primary key."""
    return str(uuid.uuid4())
