from __future__ import annotations

import unittest

from api.config import _dotenv_value, _normalize_public_url


class PublicUrlNormalizationTests(unittest.TestCase):
    def test_dotenv_value_removes_unquoted_inline_comment(self) -> None:
        self.assertEqual(
            _dotenv_value("http://localhost:8000 # API URL"),
            "http://localhost:8000",
        )

    def test_dotenv_value_preserves_hash_inside_values(self) -> None:
        self.assertEqual(
            _dotenv_value("https://example.com/#section"),
            "https://example.com/#section",
        )
        self.assertEqual(
            _dotenv_value('"secret # value" # comment'),
            "secret # value",
        )

    def test_removes_trailing_slash(self) -> None:
        self.assertEqual(
            _normalize_public_url("https://sway.example.com/"),
            "https://sway.example.com",
        )

    def test_keeps_only_origin(self) -> None:
        self.assertEqual(
            _normalize_public_url("https://sway.example.com/path?query=yes#section"),
            "https://sway.example.com",
        )

    def test_preserves_port(self) -> None:
        self.assertEqual(
            _normalize_public_url("http://localhost:3000/"),
            "http://localhost:3000",
        )


if __name__ == "__main__":
    unittest.main()
