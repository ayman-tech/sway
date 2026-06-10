from __future__ import annotations

from app.cloud.config import _dotenv_value, _normalize_url


def test_dotenv_value_removes_unquoted_inline_comment() -> None:
    assert _dotenv_value("http://localhost:8000 # API URL") == "http://localhost:8000"


def test_dotenv_value_preserves_hash_inside_values() -> None:
    assert _dotenv_value("https://example.com/#section") == "https://example.com/#section"
    assert _dotenv_value('"secret # value" # comment') == "secret # value"


def test_api_url_normalization_keeps_only_origin() -> None:
    assert (
        _normalize_url("http://localhost:8000 # accidentally loaded comment")
        == "http://localhost:8000"
    )
