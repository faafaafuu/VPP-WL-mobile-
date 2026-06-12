from __future__ import annotations

from typing import Protocol

from app.domain.models import Platform, ReceiptClaim


class ReceiptVerificationError(ValueError):
    pass


class ReceiptVerifier(Protocol):
    def verify(self, claim: ReceiptClaim) -> None:
        pass


class MvpReceiptVerifier:
    def __init__(self, allowed_product_ids: tuple[str, ...] = ("vpn.monthly",)) -> None:
        self.allowed_product_ids = allowed_product_ids

    def verify(self, claim: ReceiptClaim) -> None:
        if claim.product_id not in self.allowed_product_ids:
            raise ReceiptVerificationError("product_id is not allowed")

        if claim.platform == Platform.SANDBOX:
            if not claim.receipt.strip():
                raise ReceiptVerificationError("receipt is required")
            return

        raise ReceiptVerificationError(f"{claim.platform.value} receipt validation is not configured")
