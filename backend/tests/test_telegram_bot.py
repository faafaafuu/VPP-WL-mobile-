from __future__ import annotations

import unittest
from typing import Any

from app.repositories.memory import InMemoryRepository
from app.services.telegram_bot import TelegramBot, telegram_deep_link


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, params: dict[str, Any]) -> Any:
        self.calls.append((method, params))
        if method == "getMe":
            return {"username": "TestVpnBot"}
        return []

    def sent_texts(self) -> list[str]:
        return [params["text"] for method, params in self.calls if method == "sendMessage"]

    def sent_keyboards(self) -> list[list[list[dict[str, Any]]]]:
        return [
            params.get("reply_markup", {}).get("inline_keyboard", [])
            for method, params in self.calls
            if method == "sendMessage"
        ]

    def keyboard_buttons(self, index: int = 0) -> list[dict[str, Any]]:
        return [button for row in self.sent_keyboards()[index] for button in row]


def _bot() -> tuple[TelegramBot, FakeTransport, InMemoryRepository]:
    transport = FakeTransport()
    repository = InMemoryRepository()
    bot = TelegramBot(transport, repository, "http://84.247.166.53")
    return bot, transport, repository


def _update(chat_id: str, text: str) -> dict[str, Any]:
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": text}}


class TelegramBotTest(unittest.TestCase):
    def test_start_with_token_binds_pending_order_with_pay_button(self) -> None:
        bot, transport, repository = _bot()
        repository.create_commercial_subscription("order-token-1", "vpn.1m")

        bot.handle_update(_update("777", "/start order-token-1"))

        subscription = repository.get_commercial_subscription("order-token-1")
        self.assertEqual(subscription.tg_chat_id, "777")
        self.assertIn("Ожидаем оплату", transport.sent_texts()[0])
        buttons = transport.keyboard_buttons()
        urls = [button.get("url") for button in buttons]
        self.assertIn("http://84.247.166.53/invoice/order-token-1", urls)
        self.assertIn("http://84.247.166.53/connect/order-token-1", urls)

    def test_start_with_token_on_active_order_sends_copy_button(self) -> None:
        bot, transport, repository = _bot()
        repository.create_commercial_subscription("order-token-2", "vpn.1m")
        repository.activate_commercial_subscription("order-token-2", 30)

        bot.handle_update(_update("777", "/start order-token-2"))

        buttons = transport.keyboard_buttons()
        copy_targets = [button["copy_text"]["text"] for button in buttons if "copy_text" in button]
        urls = [button.get("url") for button in buttons]
        self.assertIn("http://84.247.166.53/sub/order-token-2", copy_targets)
        self.assertIn("http://84.247.166.53/connect/order-token-2", urls)
        self.assertNotIn("/sub/order-token-2", transport.sent_texts()[0])

    def test_start_with_unknown_token_replies_not_found(self) -> None:
        bot, transport, _ = _bot()

        bot.handle_update(_update("777", "/start no-such-token"))

        self.assertIn("не найден", transport.sent_texts()[0])

    def test_plain_message_lists_bound_orders(self) -> None:
        bot, transport, repository = _bot()
        repository.create_commercial_subscription("order-token-3", "vpn.1m")
        repository.activate_commercial_subscription("order-token-3", 30)
        repository.bind_telegram("order-token-3", "555")

        bot.handle_update(_update("555", "ссылка"))

        text = transport.sent_texts()[0]
        self.assertIn("ORDER-TOKEN-", text)
        copy_targets = [b["copy_text"]["text"] for b in transport.keyboard_buttons() if "copy_text" in b]
        self.assertIn("http://84.247.166.53/sub/order-token-3", copy_targets)

    def test_plain_message_without_bindings_sends_instructions(self) -> None:
        bot, transport, _ = _bot()

        bot.handle_update(_update("555", "/link"))

        self.assertIn("нет привязанных заказов", transport.sent_texts()[0])

    def test_notify_activated_sends_message_to_bound_chat(self) -> None:
        bot, transport, repository = _bot()
        repository.create_commercial_subscription("order-token-4", "vpn.1m")
        repository.bind_telegram("order-token-4", "999")
        subscription = repository.activate_commercial_subscription("order-token-4", 30)

        self.assertTrue(bot.notify_activated(subscription))
        text = transport.sent_texts()[0]
        self.assertIn("Оплата подтверждена", text)
        copy_targets = [b["copy_text"]["text"] for b in transport.keyboard_buttons() if "copy_text" in b]
        self.assertIn("http://84.247.166.53/sub/order-token-4", copy_targets)

    def test_notify_activated_without_binding_is_noop(self) -> None:
        bot, transport, repository = _bot()
        repository.create_commercial_subscription("order-token-5", "vpn.1m")
        subscription = repository.activate_commercial_subscription("order-token-5", 30)

        self.assertFalse(bot.notify_activated(subscription))
        self.assertEqual(transport.sent_texts(), [])

    def test_deep_link_escapes_token(self) -> None:
        link = telegram_deep_link("TestVpnBot", "abc+def")

        self.assertEqual(link, "https://t.me/TestVpnBot?start=abc%2Bdef")


class TelegramPagesTest(unittest.TestCase):
    def _service(self) -> Any:
        from app.api.service import ApiService
        from app.domain.config_builder import ConfigBuilder
        from app.security.tokens import TokenService

        return ApiService(
            InMemoryRepository(),
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin-token-xx",
            public_base_url="http://127.0.0.1:8080",
            checkout_mode="crypto_manual",
            crypto_wallets={"trc20": "TTestWalletAddress1234567890ABCDE"},
            telegram_bot_username="TestVpnBot",
        )

    def test_connect_page_shows_telegram_bind_link(self) -> None:
        svc = self._service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.connect_html(token)

        self.assertIn(f"https://t.me/TestVpnBot?start={token}", html)

    def test_invoice_page_shows_telegram_bind_link(self) -> None:
        svc = self._service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn(f"https://t.me/TestVpnBot?start={token}", html)

    def test_recover_page_mentions_bot(self) -> None:
        svc = self._service()

        html = svc.recover_html()

        self.assertIn("t.me/TestVpnBot", html)

    def test_pages_without_bot_have_no_telegram_link(self) -> None:
        svc = self._service()
        svc.telegram_bot_username = None
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        self.assertNotIn("t.me/", svc.connect_html(token))
        self.assertNotIn("t.me/", svc.recover_html())

    def test_admin_activation_calls_notifier(self) -> None:
        svc = self._service()
        notified = []
        svc.activation_notifier = notified.append
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        svc.admin_activate_commercial_subscription("test-admin-token-xx", token, {"duration_days": 30})

        self.assertEqual(len(notified), 1)
        self.assertEqual(notified[0].token, token)


class PaymentWatcherNotifyTest(unittest.TestCase):
    def test_watcher_calls_on_activated_with_bound_subscription(self) -> None:
        from decimal import Decimal

        from app.domain.tariffs import parse_tariffs, tariffs_by_id
        from app.services.chain_providers import IncomingTransfer
        from app.services.payment_watcher import PaymentWatcher

        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-watch", "vpn.1m")
        repository.set_payment_intent("tok-watch", "usdt_trc20", "2.13", "TWallet")
        repository.bind_telegram("tok-watch", "424242")

        class FakeProvider:
            def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
                return [
                    IncomingTransfer(
                        tx_id="tx-1",
                        from_address="TPayer",
                        to_address="TWallet",
                        symbol="USDT",
                        amount=Decimal("2.13"),
                        confirmations=3,
                    )
                ]

        notified = []
        watcher = PaymentWatcher(
            repository,
            {"usdt_trc20": FakeProvider()},
            tariffs_by_id(parse_tariffs(None)),
            on_activated=notified.append,
        )

        summary = watcher.run_once()

        self.assertEqual(summary.activated, 1)
        self.assertEqual(len(notified), 1)
        self.assertEqual(notified[0].tg_chat_id, "424242")


class TwentySyncTest(unittest.TestCase):
    def test_on_activated_posts_opportunity(self) -> None:
        from app.domain.tariffs import parse_tariffs, tariffs_by_id
        from app.services.twenty_sync import TwentySync

        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-crm", "vpn.1m")
        subscription = repository.activate_commercial_subscription("tok-crm", 30)
        sync = TwentySync("http://crm.local", "key", tariffs_by_id(parse_tariffs(None)))
        posted = []
        sync._post = lambda path, payload: posted.append((path, payload)) or {}

        self.assertTrue(sync.on_activated(subscription))
        path, payload = posted[0]
        self.assertEqual(path, "/rest/opportunities")
        self.assertIn("TOK-CRM", payload["name"])
        self.assertEqual(payload["amount"]["currencyCode"], "RUB")

    def test_on_activated_swallows_errors(self) -> None:
        from app.domain.tariffs import parse_tariffs, tariffs_by_id
        from app.services.twenty_sync import TwentySync

        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-crm2", "vpn.1m")
        subscription = repository.activate_commercial_subscription("tok-crm2", 30)
        sync = TwentySync("http://crm.local", "key", tariffs_by_id(parse_tariffs(None)))

        def boom(path: str, payload: dict) -> dict:
            raise RuntimeError("crm down")

        sync._post = boom

        self.assertFalse(sync.on_activated(subscription))


if __name__ == "__main__":
    unittest.main()
