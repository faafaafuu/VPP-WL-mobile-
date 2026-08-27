from __future__ import annotations

import unittest

from app.api.pages import _base_monthly_price, _tariff_row
from app.domain.tariffs import Tariff


class TariffPricingDisplayTest(unittest.TestCase):
    def test_multi_month_tariff_shows_discount_against_shortest_tariff(self) -> None:
        tariffs = (
            Tariff(id="vpn.1m", title="1 месяц", duration_days=30, price_rub="200.00"),
            Tariff(id="vpn.6m", title="6 месяцев", duration_days=180, price_rub="900.00"),
        )
        base_monthly = _base_monthly_price(tariffs)

        html = _tariff_row(1, tariffs[1], base_monthly)

        # 6 * 200 = 1200 full price vs 900 actual = 25% off
        self.assertIn('class="price-old"', html)
        self.assertIn("1200", html)  # struck-through full price
        self.assertIn("-25%", html)

    def test_shortest_tariff_shows_no_discount(self) -> None:
        tariffs = (
            Tariff(id="vpn.1m", title="1 месяц", duration_days=30, price_rub="200.00"),
            Tariff(id="vpn.6m", title="6 месяцев", duration_days=180, price_rub="900.00"),
        )
        base_monthly = _base_monthly_price(tariffs)

        html = _tariff_row(0, tariffs[0], base_monthly)

        self.assertNotIn('class="price-old"', html)
        self.assertNotIn("discount-tag", html)

    def test_single_tariff_has_no_discount_reference(self) -> None:
        tariffs = (Tariff(id="vpn.1m", title="1 месяц", duration_days=30, price_rub="200.00"),)
        base_monthly = _base_monthly_price(tariffs)

        html = _tariff_row(0, tariffs[0], base_monthly)

        self.assertNotIn('class="price-old"', html)


if __name__ == "__main__":
    unittest.main()
