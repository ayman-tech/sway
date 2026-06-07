from __future__ import annotations

import unittest

from api.config import _normalize_public_url


class PublicUrlNormalizationTests(unittest.TestCase):
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
