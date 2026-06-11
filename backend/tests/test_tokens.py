from __future__ import annotations

import unittest
from datetime import timedelta

from app.security.tokens import TokenError, TokenService


class TokenServiceTest(unittest.TestCase):
    def test_issues_and_verifies_token(self) -> None:
        service = TokenService("test-secret-with-length")
        token = service.issue("usr_1")
        claims = service.verify(token)
        self.assertEqual(claims.subject, "usr_1")

    def test_rejects_tampered_token(self) -> None:
        service = TokenService("test-secret-with-length")
        token = service.issue("usr_1")
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with self.assertRaises(TokenError):
            service.verify(tampered)

    def test_rejects_expired_token(self) -> None:
        service = TokenService("test-secret-with-length")
        token = service.issue("usr_1", ttl=timedelta(seconds=-1))
        with self.assertRaises(TokenError):
            service.verify(token)


if __name__ == "__main__":
    unittest.main()

