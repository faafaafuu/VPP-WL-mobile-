from __future__ import annotations

import hashlib

from app.domain.models import Platform


def receipt_transaction_id(platform: Platform, receipt: str) -> str:
    normalized_receipt = receipt.strip().encode("utf-8")
    digest = hashlib.sha256(normalized_receipt).hexdigest()
    return f"{platform.value}:sha256:{digest}"
