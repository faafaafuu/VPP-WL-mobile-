from __future__ import annotations

import argparse
import json
import time

from app.core.settings import load_settings
from app.domain.tariffs import tariffs_by_id
from app.repositories.factory import create_repository
from app.services.chain_providers import build_providers
from app.services.payment_watcher import PaymentWatcher


def main() -> None:
    parser = argparse.ArgumentParser(description="Match pending crypto invoices against on-chain transfers.")
    parser.add_argument("--loop", action="store_true", help="Keep running with CRYPTO_WATCH_INTERVAL_SECONDS pauses.")
    args = parser.parse_args()

    settings = load_settings()
    providers = build_providers(settings.crypto_trongrid_api_key, settings.crypto_etherscan_api_key)
    if not providers:
        parser.error("no chain providers configured")
    repository = create_repository(nodes=list(settings.nodes) if settings.nodes else None)
    watcher = PaymentWatcher(
        repository,
        providers,
        tariffs_by_id(settings.tariffs),
        min_confirmations=settings.crypto_min_confirmations,
    )

    while True:
        summary = watcher.run_once()
        print(
            json.dumps(
                {
                    "checked": summary.checked,
                    "activated": summary.activated,
                    "errors": summary.errors,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        if not args.loop:
            break
        time.sleep(max(settings.crypto_watch_interval_seconds, 10))


if __name__ == "__main__":
    main()
