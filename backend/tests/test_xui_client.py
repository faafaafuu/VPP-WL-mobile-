from __future__ import annotations

import unittest

from app.services.xui_client import HttpXuiClient


class XuiClientFieldsTest(unittest.TestCase):
    def test_total_gb_is_converted_to_bytes(self) -> None:
        fields = HttpXuiClient._client_fields("uuid-1", "email-1", 0, 0, total_gb=150)

        self.assertEqual(fields["totalGB"], 150 * 1024 ** 3)

    def test_zero_total_gb_stays_unlimited(self) -> None:
        fields = HttpXuiClient._client_fields("uuid-1", "email-1", 0, 0, total_gb=0)

        self.assertEqual(fields["totalGB"], 0)


if __name__ == "__main__":
    unittest.main()
