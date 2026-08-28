from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from app.services import freekassa_client as m


class SignRequestTest(unittest.TestCase):
    def test_sorts_fields_alphabetically_before_joining(self) -> None:
        """Regression guard for the exact FreeKassa v1 signing algorithm:
        sort fields by key (alphabetically), join their *values* with "|",
        then HMAC-SHA256 with the API key. Confirmed against FreeKassa's own
        docs and a real open-source SDK, and live-verified against
        api.fk.life (returned "Merchant not activated" rather than an
        invalid-signature error for a correctly-signed request)."""
        data = {"shopId": 777, "nonce": 123}
        signature = m.sign_request(data, "secret-key")

        # "nonce" sorts before "shopId" alphabetically, so its value must
        # come first in the joined message.
        expected_message = "123|777"
        expected = hmac.new(b"secret-key", expected_message.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(signature, expected)

    def test_signature_changes_with_any_field_value(self) -> None:
        base = {"shopId": 1, "amount": "10.00"}
        changed = {"shopId": 1, "amount": "10.01"}

        self.assertNotEqual(m.sign_request(base, "k"), m.sign_request(changed, "k"))


class CreateOrderTest(unittest.TestCase):
    def test_success_returns_parsed_response(self) -> None:
        response_body = json.dumps(
            {"type": "success", "orderId": 123, "orderHash": "abc", "location": "https://pay.freekassa.net/form/123/abc"}
        ).encode()

        with patch.object(m.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = response_body
            result = m.create_order(
                shop_id="75677",
                api_key="secret",
                i="36",
                email="buyer@example.com",
                ip="1.2.3.4",
                amount="200.00",
                payment_id="tok123",
            )

        self.assertEqual(result["location"], "https://pay.freekassa.net/form/123/abc")
        sent_body = json.loads(urlopen.call_args[0][0].data)
        self.assertEqual(sent_body["shopId"], 75677)
        self.assertEqual(sent_body["paymentId"], "tok123")
        self.assertIn("signature", sent_body)
        self.assertIn("nonce", sent_body)

    def test_error_response_raises_freekassa_error(self) -> None:
        import urllib.error

        http_error = urllib.error.HTTPError(
            url="https://api.fk.life/v1/orders/create",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        http_error.read = lambda: json.dumps({"type": "error", "message": "Merchant not activated"}).encode()

        with patch.object(m.urllib.request, "urlopen", side_effect=http_error):
            with self.assertRaises(m.FreekassaError) as ctx:
                m.create_order(
                    shop_id="75677",
                    api_key="secret",
                    i="36",
                    email="buyer@example.com",
                    ip="1.2.3.4",
                    amount="200.00",
                )

        self.assertIn("Merchant not activated", str(ctx.exception))

    def test_success_type_without_location_raises(self) -> None:
        response_body = json.dumps({"type": "success"}).encode()

        with patch.object(m.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = response_body
            with self.assertRaises(m.FreekassaError):
                m.create_order(
                    shop_id="75677",
                    api_key="secret",
                    i="36",
                    email="buyer@example.com",
                    ip="1.2.3.4",
                    amount="200.00",
                )


if __name__ == "__main__":
    unittest.main()
