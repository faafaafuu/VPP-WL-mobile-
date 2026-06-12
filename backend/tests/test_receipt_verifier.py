from __future__ import annotations

import unittest

from app.domain.models import Platform, ReceiptClaim
from app.services.receipt_verifier import MvpReceiptVerifier, ReceiptVerificationError


class ReceiptVerifierTest(unittest.TestCase):
    def test_allows_sandbox_receipts(self) -> None:
        verifier = MvpReceiptVerifier()

        verifier.verify(ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1"))

    def test_rejects_production_receipts_until_store_validation_is_configured(self) -> None:
        verifier = MvpReceiptVerifier()

        with self.assertRaises(ReceiptVerificationError):
            verifier.verify(
                ReceiptClaim(
                    platform=Platform.APPLE,
                    receipt="long-production-looking-receipt-value",
                    device_id="device-1",
                )
            )


if __name__ == "__main__":
    unittest.main()
