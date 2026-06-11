"""API key management for agent access."""

from __future__ import annotations

import hashlib
import secrets

from api.auth import CurrentUser, admin_client
from api.schemas import ApiKeyOut
from api.secret_crypto import decrypt_secret, encrypt_secret
from sway_core.datetime_utils import utc_now

_PREFIX = "sway_"


def generate_api_key(user: CurrentUser) -> ApiKeyOut:
    raw = _PREFIX + secrets.token_hex(20)
    now = utc_now()
    admin_client().table("user_settings").update({
        "api_key_hash": hashlib.sha256(raw.encode()).hexdigest(),
        "api_key_ciphertext": encrypt_secret(raw),
        "api_key_created_at": now.isoformat(),
    }).eq("user_id", user.id).execute()
    return ApiKeyOut(key=raw, created_at=now)


def get_api_key(user: CurrentUser) -> ApiKeyOut:
    res = (
        admin_client()
        .table("user_settings")
        .select("api_key_ciphertext,api_key_created_at")
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    row = res.data[0] if res.data else {}
    cipher = row.get("api_key_ciphertext")
    return ApiKeyOut(
        key=decrypt_secret(cipher) if cipher else None,
        created_at=row.get("api_key_created_at"),
    )


def revoke_api_key(user: CurrentUser) -> None:
    admin_client().table("user_settings").update({
        "api_key_hash": None,
        "api_key_ciphertext": None,
        "api_key_created_at": None,
    }).eq("user_id", user.id).execute()
