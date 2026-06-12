from __future__ import annotations

from typing import Protocol

from app.domain.models import Platform, ReceiptClaim


class ReceiptVerificationError(ValueError):
    pass


class ReceiptVerifier(Protocol):
    def verify(self, claim: ReceiptClaim) -> None:
        pass


class MvpReceiptVerifier:
    def verify(self, claim: ReceiptClaim) -> None:
        if claim.platform == Platform.SANDBOX:
            if not claim.receipt.strip():
                raise ReceiptVerificationError("receipt is required")
            return

        raise ReceiptVerificationError(f"{claim.platform.value} receipt validation is not configured")
