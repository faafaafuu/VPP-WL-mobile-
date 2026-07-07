from __future__ import annotations

import unittest
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService

_ADMIN = "test-admin-token-xx"


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token=_ADMIN,
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets={"trc20": "TTestWalletAddress1234567890ABCDE"},
    )


class InvoiceContactTest(unittest.TestCase):
    def test_saves_normalized_email(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        result = svc.set_invoice_contact(token, {"email": "  User@Example.COM "})

        self.assertEqual(result["status"], "saved")
        subscription = svc.repository.get_commercial_subscription(token)
        self.assertEqual(subscription.customer_email, "user@example.com")

    def test_rejects_invalid_email(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        for bad in ("not-an-email", "a@b", "a b@c.com", ""):
            with self.assertRaises(ApiError) as ctx:
                svc.set_invoice_contact(token, {"email": bad})
            self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_unknown_token_raises_404(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.set_invoice_contact("missing", {"email": "user@example.com"})

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_recover_by_email_case_insensitive(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "user@example.com"})

        result = svc.recover({"query": "User@Example.COM"})

        self.assertEqual(result["token"], token)

    def test_invoice_page_shows_email_form(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn('id="contactEmail"', html)
        self.assertIn(f"/invoice/' + TOKEN + '/contact", html)

    def test_admin_orders_include_email(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "user@example.com"})

        orders = svc.admin_orders(_ADMIN)["orders"]

        self.assertEqual(orders[0]["email"], "user@example.com")


class EmailSenderTest(unittest.TestCase):
    def _sender(self):
        from app.services.email_sender import EmailSender

        return EmailSender(
            "smtp.example.com", 465, "bot@example.com", "secret", "bot@example.com", "http://84.247.166.53"
        )

    def test_message_contains_links(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-mail", "vpn.1m")
        repository.set_customer_email("tok-mail", "user@example.com")
        subscription = repository.activate_commercial_subscription("tok-mail", 30)

        message = self._sender()._build_message(subscription)

        self.assertEqual(message["To"], "user@example.com")
        body = message.get_content()
        self.assertIn("http://84.247.166.53/sub/tok-mail", body)
        self.assertIn("http://84.247.166.53/connect/tok-mail", body)

    def test_on_activated_without_email_is_noop(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-noemail", "vpn.1m")
        subscription = repository.activate_commercial_subscription("tok-noemail", 30)

        self.assertFalse(self._sender().on_activated(subscription))

    def test_on_activated_swallows_smtp_errors(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-mailerr", "vpn.1m")
        repository.set_customer_email("tok-mailerr", "user@example.com")
        subscription = repository.activate_commercial_subscription("tok-mailerr", 30)
        sender = self._sender()

        def boom(message) -> None:
            raise ConnectionError("smtp down")

        sender._send = boom

        self.assertFalse(sender.on_activated(subscription))


class SmtpSettingsTest(unittest.TestCase):
    def _base_env(self) -> dict[str, str]:
        return {
            "VPN_ROUTER_TOKEN_SECRET": "test-secret-with-enough-len",
            "VPN_ROUTER_ADMIN_TOKEN": "test-admin-with-enough-len",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8080",
        }

    def test_smtp_host_requires_credentials(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {**self._base_env(), "SMTP_HOST": "smtp.example.com"}

        with self.assertRaises(SettingsError):
            load_settings(env)

    def test_full_smtp_config_ok(self) -> None:
        from app.core.settings import load_settings

        env = {
            **self._base_env(),
            "SMTP_HOST": "smtp.example.com",
            "SMTP_USER": "bot@example.com",
            "SMTP_PASSWORD": "app-password",
        }

        settings = load_settings(env)

        self.assertEqual(settings.smtp_host, "smtp.example.com")
        self.assertEqual(settings.smtp_port, 465)
        self.assertEqual(settings.smtp_from, "bot@example.com")


if __name__ == "__main__":
    unittest.main()
