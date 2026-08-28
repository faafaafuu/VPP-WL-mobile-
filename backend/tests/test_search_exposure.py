from __future__ import annotations

import unittest
from decimal import Decimal

from app.api.service import ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.exchange_rates import make_fixed_rate_service


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets={"trc20": "TTestWalletAddress1234567890ABCDE"},
        exchange_rate_service=make_fixed_rate_service({"tether": Decimal("100.00")}),
    )


class SearchExposureTest(unittest.TestCase):
    """Advertising a VPN service is prohibited in Russia, and domains reach
    the blocking registry partly by being found — including in search
    results. Sales come from Telegram, so being indexed buys nothing and
    costs exposure."""

    def test_every_page_asks_not_to_be_indexed(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        pages = [
            svc.landing_html(),
            svc.invoice_html(token),
            svc.recover_html(),
            svc.terms_html(),
            svc.privacy_html(),
        ]

        for html in pages:
            with self.subTest(title=html.split("<title>")[1].split("</title>")[0]):
                self.assertIn('<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">', html)

    def test_titles_do_not_advertise_the_service(self) -> None:
        """The title is what a search result shows in large type."""
        svc = _service()

        for html in (svc.landing_html(), svc.recover_html(), svc.terms_html()):
            title = html.split("<title>")[1].split("</title>")[0]
            with self.subTest(title=title):
                self.assertNotIn("VPN", title.upper())

    def test_description_does_not_advertise_the_service(self) -> None:
        svc = _service()

        description = svc.landing_html().split('name="description" content="')[1].split('"')[0]

        self.assertNotIn("VPN", description.upper())


if __name__ == "__main__":
    unittest.main()
