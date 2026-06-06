from datetime import date, datetime, timezone
from types import SimpleNamespace

from postgrest.exceptions import APIError

import api.availability_shares as shares
from api.availability_shares import (
    MAX_ACTIVE_SHARES,
    TOKEN_ALPHABET,
    _generate_token,
    _is_token_collision,
    _valid_token,
)


def test_active_share_limit_is_twenty() -> None:
    assert MAX_ACTIVE_SHARES == 20


def test_generate_token_uses_readable_grouped_format() -> None:
    token = _generate_token()
    groups = token.split("-")

    assert [len(group) for group in groups] == [4, 4, 4]
    assert set("".join(groups)) <= set(TOKEN_ALPHABET)
    assert _valid_token(token)


def test_valid_token_accepts_legacy_long_tokens() -> None:
    assert _valid_token("a" * 43)
    assert not _valid_token("abcd-efgh-ijkl")
    assert not _valid_token("too-short")


def test_token_collision_requires_unique_token_hash_violation() -> None:
    collision = APIError({
        "code": "23505",
        "message": 'duplicate key value violates unique constraint "availability_shares_token_hash_key"',
        "details": "Key (token_hash)=(example) already exists.",
        "hint": None,
    })
    other_unique_violation = APIError({
        "code": "23505",
        "message": 'duplicate key value violates unique constraint "availability_shares_pkey"',
        "details": "Key (id)=(example) already exists.",
        "hint": None,
    })

    assert _is_token_collision(collision)
    assert not _is_token_collision(other_unique_violation)


def test_create_share_retries_token_collision(monkeypatch) -> None:
    tokens = iter(["aaaa-bbbb-cccc", "dddd-eeee-ffff"])
    inserted_hashes: list[str] = []

    class FakeTable:
        data = []

        def insert(self, row):
            inserted_hashes.append(row["token_hash"])
            return self

        def select(self, *_args):
            return self

        def eq(self, *_args):
            return self

        def gt(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def execute(self):
            if len(inserted_hashes) == 1:
                raise APIError({
                    "code": "23505",
                    "message": "duplicate key value violates unique constraint",
                    "details": "Key (token_hash) already exists.",
                    "hint": None,
                })
            return self

    monkeypatch.setattr(shares, "_cleanup_expired", lambda: None)
    monkeypatch.setattr(shares, "_generate_token", lambda: next(tokens))
    monkeypatch.setattr(shares, "_table", lambda: FakeTable())
    monkeypatch.setattr(shares, "get_user_settings", lambda _user: SimpleNamespace(first_name="Ayman"))
    monkeypatch.setattr(
        shares,
        "get_settings",
        lambda: SimpleNamespace(web_public_url="https://sway.example"),
    )
    monkeypatch.setattr(
        shares,
        "utc_now",
        lambda: datetime(2026, 6, 6, tzinfo=timezone.utc),
    )
    payload = shares.AvailabilityShareCreate(
        creator_timezone="America/New_York",
        snapshot=shares.AvailabilitySnapshot(
            selected_dates=[date(2026, 6, 6)],
            start_hour=9,
            end_hour=10,
            available_slots={"2026-06-06": [0]},
        ),
    )

    result = shares.create_share(SimpleNamespace(id="user-id"), payload)

    assert len(inserted_hashes) == 2
    assert result.url == "https://sway.example/availability/share/dddd-eeee-ffff"
