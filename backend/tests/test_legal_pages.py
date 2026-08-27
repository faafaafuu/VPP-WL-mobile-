from __future__ import annotations

import unittest

from app.api.service import ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService


class LegalPagesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ApiService(
            InMemoryRepository(),
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            public_base_url="http://203.0.113.10:8080",
            checkout_mode="mock",
            support_email="support@example.test",
        )

    def test_terms_page_mentions_offer_and_contact(self) -> None:
        html = self.service.terms_html()

        self.assertIn("Публичная оферта", html)
        self.assertIn("support@example.test", html)

    def test_privacy_page_mentions_152_fz_and_contact(self) -> None:
        html = self.service.privacy_html()

        self.assertIn("152-ФЗ", html)
        self.assertIn("support@example.test", html)

    def test_privacy_page_without_support_email_shows_placeholder(self) -> None:
        service = ApiService(
            InMemoryRepository(),
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            checkout_mode="mock",
        )

        html = service.privacy_html()

        self.assertIn("заполнить", html)

    def test_landing_page_links_to_terms_and_privacy(self) -> None:
        html = self.service.landing_html()

        self.assertIn('href="/terms"', html)
        self.assertIn('href="/privacy"', html)


if __name__ == "__main__":
    unittest.main()
