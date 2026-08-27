from __future__ import annotations

import unittest

from app.domain.tariffs import DEFAULT_TARIFFS, parse_tariffs


class TariffTrafficLimitTest(unittest.TestCase):
    def test_default_tariffs_have_150gb_and_3_devices(self) -> None:
        for tariff in DEFAULT_TARIFFS:
            self.assertEqual(tariff.max_devices, 3)
            self.assertEqual(tariff.traffic_gb, 150)

    def test_parses_seventh_field_as_traffic_gb(self) -> None:
        tariffs = parse_tariffs("vpn.1m:1 месяц:30:200.00::3:150")

        self.assertEqual(tariffs[0].traffic_gb, 150)

    def test_omitted_traffic_gb_means_unlimited(self) -> None:
        tariffs = parse_tariffs("vpn.1m:1 месяц:30:200.00::3")

        self.assertEqual(tariffs[0].traffic_gb, 0)

    def test_rejects_negative_traffic_gb(self) -> None:
        with self.assertRaises(ValueError):
            parse_tariffs("vpn.1m:1 месяц:30:200.00::3:-10")

    def test_rejects_non_integer_traffic_gb(self) -> None:
        with self.assertRaises(ValueError):
            parse_tariffs("vpn.1m:1 месяц:30:200.00::3:many")


if __name__ == "__main__":
    unittest.main()
