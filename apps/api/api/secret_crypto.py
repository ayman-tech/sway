"""Authenticated encryption for server-managed integration secrets."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from api.config import get_settings


def encryption_available() -> bool:
    try:
        _fernet()
    except HTTPException:
        return False
    return True


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stored Google credentials cannot be decrypted. Re-enter the credentials.",
        ) from exc


def _fernet() -> Fernet:
    key = get_settings().google_credentials_encryption_key
    if not key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google setup is unavailable until GOOGLE_CREDENTIALS_ENCRYPTION_KEY is configured.",
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "GOOGLE_CREDENTIALS_ENCRYPTION_KEY is invalid.",
        ) from exc
