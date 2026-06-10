from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

import api.google_integration as google
import api.secret_crypto as crypto


NOW = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)


class FakeQuery:
    def __init__(self, data=None):
        self.data = data or []
        self.updates: list[dict] = []

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def update(self, values):
        self.updates.append(values)
        return self

    def upsert(self, values):
        self.updates.append(values)
        return self

    def or_(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


def test_secret_encryption_round_trip_and_no_plaintext(monkeypatch) -> None:
    key = crypto.Fernet.generate_key().decode()
    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: SimpleNamespace(google_credentials_encryption_key=key),
    )

    encrypted = crypto.encrypt_secret("super-secret")

    assert encrypted != "super-secret"
    assert crypto.decrypt_secret(encrypted) == "super-secret"


def test_missing_encryption_key_disables_setup(monkeypatch) -> None:
    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: SimpleNamespace(google_credentials_encryption_key=None),
    )

    assert not crypto.encryption_available()
    try:
        crypto.encrypt_secret("secret")
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Missing encryption key should fail.")


def test_google_status_never_returns_secret(monkeypatch) -> None:
    monkeypatch.setattr(google, "_row_for_user", lambda _user_id: {
        "oauth_client_id": "client-id",
        "oauth_client_secret_ciphertext": "ciphertext",
        "token_ciphertext": "token-ciphertext",
        "account_email": "a@example.com",
    })
    monkeypatch.setattr(google, "encryption_available", lambda: True)
    monkeypatch.setattr(
        google,
        "get_settings",
        lambda: SimpleNamespace(google_redirect_uri="https://api.example/google/callback"),
    )

    status = google.google_status(SimpleNamespace(id="user-id"))

    assert status.configured
    assert status.connected
    assert status.client_id == "client-id"
    assert "secret" not in status.model_dump()


def test_automatic_sync_respects_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(google, "utc_now", lambda: NOW)

    assert not google._acquire_sync_lease({
        "user_id": "user-id",
        "last_synced_at": (NOW - timedelta(minutes=1)).isoformat(),
    }, force=False)


def test_forced_sync_bypasses_cooldown_and_acquires_lease(monkeypatch) -> None:
    table = FakeQuery(data=[{"user_id": "user-id"}])
    monkeypatch.setattr(google, "utc_now", lambda: NOW)
    monkeypatch.setattr(google, "_table", lambda: table)

    acquired = google._acquire_sync_lease({
        "user_id": "user-id",
        "last_synced_at": (NOW - timedelta(minutes=1)).isoformat(),
    }, force=True)

    assert acquired
    assert table.updates == [{"sync_lease_until": (NOW + google.SYNC_LEASE).isoformat()}]


def test_disconnect_retains_encrypted_client_credentials(monkeypatch) -> None:
    table = FakeQuery(data=[{"user_id": "user-id"}])
    monkeypatch.setattr(google, "utc_now", lambda: NOW)
    monkeypatch.setattr(google, "_table", lambda: table)

    google.disconnect(SimpleNamespace(id="user-id"))

    update = table.updates[0]
    assert "oauth_client_id" not in update
    assert "oauth_client_secret_ciphertext" not in update
    assert update["token_ciphertext"] is None


def test_expired_oauth_state_is_rejected_before_token_exchange(monkeypatch) -> None:
    row = {
        "user_id": "user-id",
        "oauth_state_created_at": (NOW - google.OAUTH_STATE_LIFETIME - timedelta(seconds=1)).isoformat(),
    }
    admin = SimpleNamespace(table=lambda _name: FakeQuery(data=[row]))
    monkeypatch.setattr(google, "admin_client", lambda: admin)
    monkeypatch.setattr(google, "utc_now", lambda: NOW)
    monkeypatch.setattr(google, "_flow", lambda _row: (_ for _ in ()).throw(AssertionError("flow used")))

    try:
        google.oauth_callback("code", "state")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "expired" in str(exc.detail).lower()
    else:
        raise AssertionError("Expired OAuth state should fail.")


def test_failed_sync_releases_lease_and_records_error(monkeypatch) -> None:
    table = FakeQuery(data=[{"user_id": "user-id"}])
    row = {"user_id": "user-id", "token_ciphertext": "encrypted"}
    monkeypatch.setattr(google, "_row_for_user", lambda _user_id: row)
    monkeypatch.setattr(google, "_acquire_sync_lease", lambda _row, _force: True)
    monkeypatch.setattr(google, "_import_google", lambda _user, _row: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(google, "_table", lambda: table)
    monkeypatch.setattr(google, "utc_now", lambda: NOW)

    try:
        google.sync_google(SimpleNamespace(id="user-id"))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Sync failure should surface.")

    assert table.updates[-1]["sync_lease_until"] is None
    assert table.updates[-1]["last_sync_error"] == "boom"
