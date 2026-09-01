from __future__ import annotations

import base64
import hmac
import re
import uuid as uuid_module
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal
from http import HTTPStatus
from typing import Any

from app.api.pages import (
    admin_orders_page,
    connect_page,
    freekassa_result_page,
    invoice_page,
    landing_page,
    privacy_page,
    recover_page,
    terms_page,
)
from app.domain.coins import ALL_COINS, COINS_BY_ID, Coin
from app.domain.solana_tx import SolanaTxError, build_transfer_message
from app.services.chain_providers import ChainProviderError
from app.domain.wallet_connect import payment_units, payment_uri, transfer_spec, wallet_links
from app.domain.config_builder import ConfigBuilder
from app.domain.config_validation import ConfigValidationError, validate_config_shape
from app.domain.models import AdminAuditEvent, CommercialSubscription, NodeHealth, NodeStatus, Platform, Protocol, ReceiptClaim, VlessOptions, VpnNode, new_id, new_subscription_token
from app.domain.node_scoring import node_score
from app.domain.node_selection import choose_preferred_nodes
from app.domain.qr_svg import fits as qr_fits, qr_svg
from app.domain.tariffs import Tariff, parse_tariffs, tariffs_by_id
from app.domain.unique_amount import AmountCollisionError, unique_coin_amount
from app.domain.singbox_config import singbox_config_json
from app.domain.v2ray_subscription import encoded_subscription, hysteria2_link, raw_subscription
from app.repositories.factory import Repository
from app.security.tokens import TokenError, TokenService
from app.services.exchange_rates import ExchangeRateService
from app.services.freekassa_client import FreekassaError, create_order as freekassa_create_order
from app.services.receipt_verifier import MvpReceiptVerifier, ReceiptVerifier
from app.services.xui_client import DisabledXuiClient, XuiClient, XuiClientError
from app.services.yookassa import DisabledYooKassaProvider, YooKassaError, YooKassaProvider



@dataclass(frozen=True)
class ApiError(Exception):
    status: HTTPStatus
    payload: dict[str, Any]


class ApiService:
    def __init__(
        self,
        repository: Repository,
        token_service: TokenService,
        config_builder: ConfigBuilder,
        admin_token: str,
        receipt_verifier: ReceiptVerifier | None = None,
        yookassa_provider: YooKassaProvider | None = None,
        public_base_url: str = "http://127.0.0.1:8080",
        checkout_mode: str = "mock",
        tariffs: tuple[Tariff, ...] | None = None,
        crypto_usdt_trc20_address: str | None = None,
        crypto_usdt_rate_rub: str = "90.00",
        crypto_wallets: dict[str, str] | None = None,
        exchange_rate_service: ExchangeRateService | None = None,
        telegram_bot_username: str | None = None,
        activation_notifier: Any = None,
        hysteria2: dict[str, Any] | None = None,
        xui_client: XuiClient | None = None,
        xui_node_template: VpnNode | None = None,
        support_email: str | None = None,
        freekassa_shop_id: str | None = None,
        freekassa_api_key: str | None = None,
        freekassa_payment_system_i: str = "36",
        watchable_coin_ids: frozenset[str] | None = None,
        chain_providers: dict[str, Any] | None = None,
    ) -> None:
        if not admin_token:
            raise ValueError("admin token is required")
        self.repository = repository
        self.token_service = token_service
        self.config_builder = config_builder
        self.admin_token = admin_token
        self.receipt_verifier = receipt_verifier or MvpReceiptVerifier()
        self.yookassa_provider = yookassa_provider or DisabledYooKassaProvider()
        self.public_base_url = public_base_url.rstrip("/")
        self.checkout_mode = checkout_mode
        self.tariffs = tariffs or parse_tariffs(None)
        self.tariffs_by_id = tariffs_by_id(self.tariffs)
        self.crypto_usdt_trc20_address = crypto_usdt_trc20_address
        self.crypto_usdt_rate_rub = crypto_usdt_rate_rub
        # wallets dict: wallet_key → address (e.g. "trc20" → "TXxx...")
        _wallets = dict(crypto_wallets or {})
        if crypto_usdt_trc20_address and "trc20" not in _wallets:
            _wallets["trc20"] = crypto_usdt_trc20_address
        self.crypto_wallets = _wallets
        self.exchange_rate_service = exchange_rate_service or ExchangeRateService("fixed")
        # both may be set after construction, once the bot username is known
        self.telegram_bot_username = telegram_bot_username
        self.activation_notifier = activation_notifier
        self.hysteria2 = hysteria2 or {}
        self.xui_client = xui_client or DisabledXuiClient()
        self.xui_node_template = xui_node_template
        self.support_email = support_email
        self.freekassa_shop_id = freekassa_shop_id
        self.freekassa_api_key = freekassa_api_key
        self.freekassa_payment_system_i = freekassa_payment_system_i
        # None = no filtering (tests and setups without a payment watcher).
        self.watchable_coin_ids = watchable_coin_ids
        # Only the Solana one is used here, to fetch a recent blockhash
        # for a transfer the buyer's browser wallet will sign.
        self.chain_providers = chain_providers or {}

    def auth_init(self, payload: dict[str, Any]) -> dict[str, Any]:
        device_id = str(payload.get("device_id", "")).strip()
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "device_id is required"})
        user = self.repository.get_or_create_user(device_id)
        return {"user_id": user.id}

    def version(self) -> dict[str, Any]:
        return {
            "api_version": "0.1.0",
            "config_format": "sing-box",
            "config_version": 1,
            "min_client_version": "0.1.0",
            "features": [
                "smart-routing",
                "node-scoring",
                "last-known-good-config",
                "expo-native-vpn-boundary",
                "account-data-export",
                "account-deletion",
                "admin-audit",
                "yookassa-payments",
                "v2ray-subscription-link-mvp",
            ],
        }

    def landing_html(self) -> str:
        return landing_page(self.tariffs)

    def terms_html(self) -> str:
        return terms_page(self.support_email)

    def privacy_html(self) -> str:
        return privacy_page(self.support_email)

    def freekassa_success_html(self) -> str:
        return freekassa_result_page(success=True, support_email=self.support_email)

    def freekassa_failure_html(self) -> str:
        return freekassa_result_page(success=False, support_email=self.support_email)

    def freekassa_pay_redirect_url(self, token: str, client_ip: str) -> str:
        """Where the "Оплатить картой" button should send the browser.

        Creates a real per-order FreeKassa payment form via the signed REST
        API (POST /orders/create), so the amount always matches the tariff
        the customer actually picked and the payment carries our order token.

        There is deliberately no static-widget fallback: that widget is
        hardcoded to one amount and carries no order reference, so for every
        tariff but one it charged the wrong sum, and even for that one there
        was no way to tell whose order the money belonged to. When the API
        call fails the caller gets 503 and every tariff behaves identically.
        """
        subscription = self._commercial_subscription(token)
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        if tariff is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "tariff not found"})
        if not self._contact_known(subscription):
            raise ApiError(HTTPStatus.CONFLICT, {"error": "contact required"})

        def unavailable(reason: str) -> str:
            self.repository.add_admin_audit_event(
                AdminAuditEvent(
                    id=new_id("aae"),
                    occurred_at=datetime.now(timezone.utc),
                    action="freekassa.order_create_failed",
                    target_type="commercial_subscription",
                    target_id=_mask_token(token),
                    result="unavailable",
                    details={"error": reason, "tariff_id": tariff.id},
                )
            )
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "card payment temporarily unavailable"})

        if not (self.freekassa_shop_id and self.freekassa_api_key):
            return unavailable("freekassa API credentials not configured")
        email = subscription.customer_email or f"guest-{token[:10]}@cleohop.ru"
        try:
            order = freekassa_create_order(
                shop_id=self.freekassa_shop_id,
                api_key=self.freekassa_api_key,
                i=self.freekassa_payment_system_i,
                email=email,
                ip=client_ip or "127.0.0.1",
                amount=tariff.price_rub,
                currency="RUB",
                payment_id=token,
            )
        except FreekassaError as exc:
            return unavailable(str(exc))
        return str(order["location"])

    def checkout(self, payload: dict[str, Any]) -> dict[str, Any]:
        tariff = self._tariff_from_payload(payload)
        token = new_subscription_token()
        self.repository.create_commercial_subscription(token, tariff.id)
        connect_url = f"/connect/{token}"

        if self.checkout_mode == "mock":
            subscription = self.repository.activate_commercial_subscription(token, tariff.duration_days)
            if subscription is None:
                raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "subscription create failed"})
            self._provision_xui_client(token)
            return {"redirect_url": connect_url, "token": token, "mode": "mock"}

        if self.checkout_mode == "crypto_manual":
            return {"redirect_url": f"/invoice/{token}", "token": token, "mode": "crypto_manual"}

        try:
            payment = self.yookassa_provider.create_payment(
                device_id=token,
                product_id=tariff.id,
                return_url=f"{self.public_base_url}{connect_url}",
            )
        except YooKassaError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc
        return {
            "redirect_url": payment.confirmation_url or connect_url,
            "token": token,
            "mode": "yookassa",
            "payment_id": payment.id,
        }

    def connect_html(self, token: str) -> str:
        subscription = self._commercial_subscription(token)
        invoice_url = f"/invoice/{subscription.token}" if self.checkout_mode == "crypto_manual" else None
        return connect_page(
            subscription,
            self.subscription_url(token),
            self.tariffs,
            invoice_url=invoice_url,
            telegram_link=self._telegram_link(token),
        )

    def invoice_html(self, token: str, card_error: str | None = None) -> str:
        subscription = self._commercial_subscription(token)
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        if tariff is None:
            raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "tariff not found"})
        if not self.crypto_wallets:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "crypto payments not configured"})
        coin_options = _build_coin_options(tariff.price_rub, self.crypto_wallets, self.exchange_rate_service)
        if self.watchable_coin_ids is not None:
            # Never offer a coin whose incoming payment nothing can confirm —
            # the customer would pay and the order would sit "pending" forever.
            coin_options = [opt for opt in coin_options if opt["id"] in self.watchable_coin_ids]
        if not coin_options:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "no configured crypto wallets"})
        for option in coin_options:
            option["pay_qr_url"] = self.payment_qr_path(token, option["id"], option.get("pay_uri"))
        return invoice_page(
            subscription,
            tariff,
            coin_options,
            telegram_link=self._telegram_link(token),
            card_error=card_error,
        )

    def _telegram_link(self, token: str) -> str | None:
        if not self.telegram_bot_username:
            return None
        from app.services.telegram_bot import telegram_deep_link

        return telegram_deep_link(self.telegram_bot_username, token)

    @staticmethod
    def _contact_known(subscription: CommercialSubscription) -> bool:
        """Whether we have any way to reach this buyer other than the order
        URL itself. Without one, a payment that lands after the customer has
        closed the tab leaves us holding a key with nobody to hand it to —
        so payment is gated on this, not merely nudged."""
        return bool((subscription.customer_email or "").strip() or (subscription.tg_chat_id or "").strip())

    def set_invoice_contact(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._commercial_subscription(token)
        email = str(payload.get("email", "")).strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "invalid email"})
        subscription = self.repository.set_customer_email(token, email)
        if subscription is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "subscription not found"})
        return {"status": "saved", "email": email, "contact": True}

    def select_invoice_coin(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        subscription = self._commercial_subscription(token)
        if subscription.is_active():
            return self.invoice_status(token)
        coin_id = str(payload.get("coin_id", "")).strip()
        coin = COINS_BY_ID.get(coin_id)
        if coin is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "unknown coin_id"})
        address = self.crypto_wallets.get(coin.wallet_key)
        if not address:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "coin not configured"})
        if not self._contact_known(subscription):
            raise ApiError(HTTPStatus.CONFLICT, {"error": "contact required"})
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        if tariff is None:
            raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "tariff not found"})

        # Reloading the page must not change the amount the user was told to send.
        if subscription.pay_coin_id == coin_id and subscription.pay_amount and subscription.pay_address == address:
            return self._payment_intent_response(subscription.token, coin, subscription.pay_amount, address)

        base_amount = self.exchange_rate_service.coin_amount(tariff.price_rub, coin)
        if base_amount is None:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "exchange rate unavailable"})
        taken = {
            other.pay_amount
            for other in self.repository.list_commercial_subscriptions(status="pending")
            if other.token != token
            and other.pay_coin_id == coin_id
            and other.pay_address == address
            and other.pay_amount
        }
        try:
            amount = unique_coin_amount(base_amount, coin, taken)
        except AmountCollisionError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc
        updated = self.repository.set_payment_intent(token, coin_id, amount, address)
        if updated is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "subscription not found"})
        return self._payment_intent_response(token, coin, amount, address)

    def invoice_status(self, token: str) -> dict[str, Any]:
        subscription = self._commercial_subscription(token)
        active = subscription.is_active()
        return {
            "status": "active" if active else subscription.status,
            "paid": bool(subscription.paid_tx) or active,
            "connect_url": f"/connect/{token}",
            "expires_at": subscription.expires_at.isoformat() if subscription.expires_at else None,
            # The invoice page polls this to unlock the payment step the
            # moment the buyer finishes binding Telegram in another tab.
            "contact": self._contact_known(subscription),
            "contact_email": subscription.customer_email or "",
            "contact_telegram": bool((subscription.tg_chat_id or "").strip()),
        }

    @staticmethod
    def payment_qr_path(token: str, coin_id: str, uri: str | None) -> str | None:
        """Where the payment QR lives, or None when this request cannot be
        drawn as one. EIP-681 token transfers run past the encoder's capacity,
        and offering a button that 503s is worse than offering none."""
        return f"/invoice/{token}/payqr/{coin_id}" if uri and qr_fits(uri) else None

    def _payment_intent_response(self, token: str, coin: Coin, amount: str, address: str) -> dict[str, Any]:
        uri = payment_uri(coin.id, address, amount)
        return {
            "status": "pending",
            "coin_id": coin.id,
            "label": coin.label,
            "network_label": coin.network_label,
            "amount": amount,
            "address": address,
            "qr_url": f"/invoice/{token}/qr/{coin.id}",
            # The amount is only final here, so the one-tap link and its QR
            # have to be rebuilt now rather than at page-render time.
            "pay_uri": uri,
            "pay_units": payment_units(coin.id, amount),
            "pay_qr_url": self.payment_qr_path(token, coin.id, uri),
            # Rebuilt with the final amount so every wallet button carries the
            # sum the payment watcher is actually waiting for.
            "wallets": wallet_links(coin.id, address, amount),
        }

    def invoice_wallet_qr_svg(self, token: str, coin_id: str | None = None) -> str:
        self._commercial_subscription(token)
        address = self._wallet_address_for_coin(coin_id)
        if not address:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "crypto payments not configured"})
        return qr_svg(address)

    def solana_transfer_message(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        """An unsigned SOL transfer for the buyer's browser wallet to sign.

        Phantom's desktop extension never registers the solana: URI scheme —
        it injects a provider instead — so the payment link does nothing
        there. The page hands this to that provider.
        """
        subscription = self._commercial_subscription(token)
        if not self._contact_known(subscription):
            raise ApiError(HTTPStatus.CONFLICT, {"error": "contact required"})
        sender = str(payload.get("from", "")).strip()
        if not sender:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "missing sender"})

        coin = COINS_BY_ID["sol"]
        address = self.crypto_wallets.get(coin.wallet_key)
        if not address:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "coin not configured"})
        amount = subscription.pay_amount if subscription.pay_coin_id == "sol" else None
        if not amount:
            raise ApiError(HTTPStatus.CONFLICT, {"error": "select the coin first"})
        lamports = payment_units("sol", amount)
        if not lamports:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "amount unavailable"})

        if sender == address:
            # The merchant's own wallet, which happens whenever the shop
            # owner tests with it. Solana rejects a self-transfer outright.
            raise ApiError(HTTPStatus.CONFLICT, {"error": "same_account"})

        provider = (self.chain_providers or {}).get("sol")
        if provider is None or not hasattr(provider, "latest_blockhash"):
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "solana rpc unavailable"})
        try:
            blockhash = provider.latest_blockhash()
            message = build_transfer_message(sender, address, int(lamports), blockhash)
        except (ChainProviderError, SolanaTxError) as exc:
            # Codes, not prose: the page renders these to the buyer, and it
            # renders them in Russian.
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "build_failed", "detail": str(exc)}) from exc
        return {"message": message, "amount": amount, "address": address}

    def invoice_payment_qr_svg(self, token: str, coin_id: str) -> str:
        """QR of the full payment request — recipient, network and amount.

        Distinct from invoice_wallet_qr_svg, which stays a bare address: an
        exchange withdrawal screen scans a QR expecting an address and
        chokes on a URI. This one is for wallet apps, where it removes the
        retyping that causes wrong-amount transfers.
        """
        subscription = self._commercial_subscription(token)
        coin = COINS_BY_ID.get(coin_id)
        if coin is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "unknown coin_id"})
        address = self.crypto_wallets.get(coin.wallet_key)
        if not address:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "coin not configured"})
        amount = subscription.pay_amount if subscription.pay_coin_id == coin_id else None
        if not amount:
            tariff = self.tariffs_by_id.get(subscription.tariff_id)
            amount = self.exchange_rate_service.coin_amount(tariff.price_rub, coin) if tariff else None
        uri = payment_uri(coin_id, address, amount or "")
        if not uri:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "coin has no payment uri"})
        if not qr_fits(uri):
            # EIP-681 token transfers run past what the encoder holds. Better
            # to say so than to raise on a request path and hand the buyer a
            # 502 in the middle of paying.
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "qr_too_long"})
        return qr_svg(uri)

    def _wallet_address_for_coin(self, coin_id: str | None) -> str | None:
        if coin_id:
            coin = COINS_BY_ID.get(coin_id)
            if coin:
                return self.crypto_wallets.get(coin.wallet_key)
        # fallback: first configured wallet
        for coin in ALL_COINS:
            addr = self.crypto_wallets.get(coin.wallet_key)
            if addr:
                return addr
        return None

    def subscription_url(self, token: str) -> str:
        return f"{self.public_base_url}/sub/{token}"

    def _extra_subscription_links(self) -> list[str]:
        """Extra non-VLESS links prepended to the subscription.

        Off by default: the only such node is hysteria2 on the German box,
        which RU mobile carriers drop (see hysteria2_link). Clients dial
        subscription entries in order, so shipping a dead first entry made
        every subscription look broken on mobile.
        """
        hy = self.hysteria2
        if not hy.get("in_subscription"):
            return []
        if hy.get("host") and hy.get("password"):
            return [
                hysteria2_link(
                    host=hy["host"],
                    port=int(hy.get("port", 36712)),
                    password=hy["password"],
                    sni=hy.get("sni") or hy["host"],
                    insecure=bool(hy.get("insecure")),
                    obfs_password=hy.get("obfs_password"),
                )
            ]
        return []

    def v2ray_subscription(self, token: str) -> str:
        self._require_active_commercial_subscription(token)
        try:
            return encoded_subscription(self._subscription_nodes(token), extra_links=self._extra_subscription_links())
        except ValueError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc

    def raw_v2ray_subscription(self, token: str) -> str:
        self._require_active_commercial_subscription(token)
        try:
            return raw_subscription(self._subscription_nodes(token), extra_links=self._extra_subscription_links())
        except ValueError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc

    def singbox_subscription(self, token: str) -> str:
        """Full sing-box profile, DNS resolved over DoH inside the tunnel.

        Offered alongside the vless:// list rather than replacing it: the plain
        list is what V2Box and older clients understand, while this is the only
        form that takes name resolution away from the carrier.
        """
        self._require_active_commercial_subscription(token)
        try:
            return singbox_config_json(self._subscription_nodes(token))
        except ValueError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc

    def _subscription_nodes(self, token: str) -> list[VpnNode]:
        """Shared-UUID nodes plus, when a 3x-ui client was provisioned for this
        subscription, a per-user node built from the xui template + that client's
        own uuid — so this one subscriber's link is individually revocable."""
        nodes = list(self.repository.list_nodes())
        subscription = self.repository.get_commercial_subscription(token)
        if subscription and subscription.xui_uuid and self.xui_node_template is not None:
            per_user_options = replace(self.xui_node_template.options, uuid=subscription.xui_uuid)
            per_user_node = replace(
                self.xui_node_template,
                id=f"xui_{token[:12]}",
                tag=f"vless-xui-{token[:8]}",
                options=per_user_options,
            )
            nodes = [per_user_node] + nodes
        return nodes

    def provision_paid_subscription(self, token: str) -> None:
        """Create this subscription's VPN client after an off-request payment.

        The crypto payment watcher activates orders straight through the
        repository, so unlike the checkout and admin paths it never went
        through provisioning — orders came out "active" with no xui_uuid and
        therefore no subscription link for the customer. Idempotent: an
        already-provisioned subscription just gets its expiry resynced.
        """
        self._provision_xui_client(token)

    def _provision_xui_client(self, token: str) -> None:
        """Best-effort: create (or, on renewal, resync the expiry/device-limit of)
        this subscription's own 3x-ui client, so it stays individually revocable
        instead of sharing the static node credential. Never raises — a panel
        outage must not block payment activation."""
        if self.xui_node_template is None or isinstance(self.xui_client, DisabledXuiClient):
            return
        subscription = self.repository.get_commercial_subscription(token)
        if subscription is None:
            return
        expiry_ms = int(subscription.expires_at.timestamp() * 1000) if subscription.expires_at else 0
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        limit_ip = tariff.max_devices if tariff else 3
        total_gb = tariff.traffic_gb if tariff else 0

        if subscription.xui_uuid:
            try:
                self.xui_client.update_client(
                    subscription.xui_uuid,
                    subscription.xui_email or f"sub-{token[:12]}",
                    expiry_time_ms=expiry_ms,
                    limit_ip=limit_ip,
                    total_gb=total_gb,
                )
            except XuiClientError:
                pass
            return

        client_uuid = str(uuid_module.uuid4())
        email = f"sub-{token[:12]}"
        try:
            self.xui_client.add_client(
                client_uuid, email, expiry_time_ms=expiry_ms, limit_ip=limit_ip, total_gb=total_gb
            )
        except XuiClientError:
            return
        self.repository.set_subscription_xui_client(token, client_uuid, email)

    def _revoke_xui_client(self, token: str) -> None:
        subscription = self.repository.get_commercial_subscription(token)
        if subscription is None or not subscription.xui_uuid or not subscription.xui_email:
            return
        try:
            self.xui_client.delete_client(subscription.xui_email)
        except XuiClientError:
            pass
        self.repository.clear_subscription_xui_client(token)

    def subscription_headers(self, token: str) -> dict[str, str]:
        """Branding headers understood by v2rayN / v2rayNG / Hiddify."""
        title = base64.b64encode("⚡ Клео".encode("utf-8")).decode("ascii")
        headers = {
            "profile-title": f"base64:{title}",
            "profile-update-interval": "12",
            "profile-web-page-url": f"{self.public_base_url}/connect/{token}",
        }
        subscription = self.repository.get_commercial_subscription(token)
        if subscription and subscription.expires_at:
            expire = int(subscription.expires_at.timestamp())
            headers["subscription-userinfo"] = f"upload=0; download=0; total=0; expire={expire}"
        return headers

    def subscription_qr_svg(self, token: str) -> str:
        self._require_active_commercial_subscription(token)
        try:
            return qr_svg(self.subscription_url(token))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": str(exc)}) from exc

    def admin_cancel_commercial_subscription(self, admin_token: str, token: str) -> dict[str, Any]:
        """Cancel one pending order. Paid orders are refused, not silently
        ignored, so a mistyped token can't quietly revoke someone's access."""
        self._require_admin(admin_token)
        subscription = self.repository.get_commercial_subscription(token)
        if subscription is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "subscription not found"})
        if subscription.status != "pending":
            raise ApiError(
                HTTPStatus.CONFLICT,
                {"error": f"only pending orders can be cancelled (status: {subscription.status})"},
            )
        cancelled = self.repository.cancel_commercial_subscription(token)
        if cancelled is None:
            raise ApiError(HTTPStatus.CONFLICT, {"error": "order is no longer pending"})
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="commercial_subscription.cancel",
                target_type="commercial_subscription",
                target_id=_mask_token(token),
                result="success",
                details={"reason": "admin"},
            )
        )
        return {"token": token, "status": cancelled.status}

    def cancel_stale_pending_orders(self, ttl_hours: int) -> int:
        """Cancel abandoned invoices so they stop piling up in the order list.

        Returns the number cancelled. A zero/negative TTL disables the sweep.
        """
        if ttl_hours <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        tokens = self.repository.cancel_stale_pending_subscriptions(cutoff)
        if tokens:
            self.repository.add_admin_audit_event(
                AdminAuditEvent(
                    id=new_id("aae"),
                    occurred_at=datetime.now(timezone.utc),
                    action="commercial_subscription.cancel_stale",
                    target_type="commercial_subscription",
                    target_id=f"{len(tokens)} orders",
                    result="success",
                    details={"ttl_hours": ttl_hours, "cancelled": len(tokens)},
                )
            )
        return len(tokens)

    def admin_activate_commercial_subscription(
        self,
        admin_token: str,
        token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_admin(admin_token)
        try:
            duration_days = int(payload.get("duration_days", 30))
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "duration_days must be an integer"}) from exc
        if duration_days <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "duration_days must be positive"})
        paid_tx = str(payload.get("paid_tx") or "").strip() or None
        payer = str(payload.get("payer") or "").strip() or None
        payment_id = str(payload.get("payment_id") or "").strip() or None
        subscription = self.repository.activate_commercial_subscription(
            token,
            duration_days,
            payment_id=payment_id,
            paid_tx=paid_tx,
            payer=payer,
        )
        if subscription is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "subscription not found"})
        self._provision_xui_client(token)
        details: dict[str, Any] = {"duration_days": duration_days}
        if paid_tx:
            details["paid_tx"] = paid_tx
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="commercial_subscription.activate",
                target_type="commercial_subscription",
                target_id=_mask_token(token),
                result="success",
                details=details,
            )
        )
        if self.activation_notifier is not None:
            try:
                self.activation_notifier(subscription)
            except Exception:  # notification failures must not block activation
                pass
        return {
            "status": "activated",
            "expires_at": subscription.expires_at.isoformat() if subscription.expires_at else None,
        }

    def admin_orders(self, admin_token: str, include_cancelled: bool = False) -> dict[str, Any]:
        self._require_admin(admin_token)
        orders = self._orders_newest_first(include_cancelled)
        return {"orders": [_admin_order(subscription) for subscription in orders]}

    def admin_orders_html(self, admin_token: str, include_cancelled: bool = False) -> str:
        self._require_admin(admin_token)
        orders = self._orders_newest_first(include_cancelled)
        return admin_orders_page([_admin_order(subscription) for subscription in orders])

    def recover_html(self, error: str | None = None) -> str:
        return recover_page(error, telegram_bot=self.telegram_bot_username)

    def recover(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query", "")).strip().lower()
        if len(query) < 8:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "query too short"})
        # Recover only by something exclusively known to the buyer: the email
        # they chose to give us. Both the sender address AND the transaction
        # hash are deliberately excluded — for a shared receiving wallet, every
        # incoming transfer's TxID and sender address are equally visible to
        # anyone browsing that wallet on a public block explorer, so accepting
        # either as "proof of payment" would let a third party who has never
        # paid us anything recover another buyer's link just by reading our
        # wallet's public transaction history. TxID lookup stays available to
        # admins (who separately verify identity) via admin_orders.
        matches = [
            subscription
            for subscription in self.repository.list_commercial_subscriptions()
            if query and query == (subscription.customer_email or "").strip().lower()
        ]
        if not matches:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "payment not found"})
        latest = max(matches, key=lambda subscription: subscription.created_at)
        return {"redirect_url": f"/connect/{latest.token}", "token": latest.token}

    def _orders_newest_first(self, include_cancelled: bool = False) -> list[Any]:
        subscriptions = self.repository.list_commercial_subscriptions()
        if not include_cancelled:
            # Abandoned invoices are the bulk of the table and carry no money;
            # hide them by default so real orders stay readable.
            subscriptions = [s for s in subscriptions if s.status != "cancelled"]
        return sorted(
            subscriptions,
            key=lambda subscription: subscription.created_at,
            reverse=True,
        )

    def prometheus_metrics(self) -> str:
        nodes = self.repository.list_nodes()
        usable_nodes = [node for node in nodes if node.is_usable()]
        health_event_counts = self.repository.count_node_health_events_by_result()
        lines = [
            "# HELP vpn_router_info Static VPN Router backend info.",
            "# TYPE vpn_router_info gauge",
            'vpn_router_info{version="0.1.0",config_format="sing-box"} 1',
            "# HELP vpn_router_repository_info Repository backend type.",
            "# TYPE vpn_router_repository_info gauge",
            f'vpn_router_repository_info{{backend="{_metric_escape(_repository_backend_name(self.repository))}"}} 1',
            "# HELP vpn_router_nodes_total VPN nodes grouped by non-sensitive routing metadata.",
            "# TYPE vpn_router_nodes_total gauge",
        ]
        node_groups: dict[tuple[str, str, str, str], int] = {}
        for node in nodes:
            key = (node.region, node.protocol.value, node.status.value, node.health.value)
            node_groups[key] = node_groups.get(key, 0) + 1
        for region, protocol, status, health in sorted(node_groups):
            lines.append(
                "vpn_router_nodes_total"
                f'{{region="{_metric_escape(region)}",protocol="{protocol}",status="{status}",health="{health}"}} '
                f"{node_groups[(region, protocol, status, health)]}"
            )
        lines.extend(
            [
                "# HELP vpn_router_usable_nodes Currently usable VPN nodes.",
                "# TYPE vpn_router_usable_nodes gauge",
                f"vpn_router_usable_nodes {len(usable_nodes)}",
                "# HELP vpn_router_node_health_events_retained Retained node health audit events grouped by probe result.",
                "# TYPE vpn_router_node_health_events_retained gauge",
                f'vpn_router_node_health_events_retained{{result="success"}} {health_event_counts.get("success", 0)}',
                f'vpn_router_node_health_events_retained{{result="failure"}} {health_event_counts.get("failure", 0)}',
                "# HELP vpn_router_admin_audit_events_retained Retained admin audit events.",
                "# TYPE vpn_router_admin_audit_events_retained gauge",
                f"vpn_router_admin_audit_events_retained {self.repository.count_admin_audit_events()}",
            ]
        )
        return "\n".join(lines) + "\n"

    def auth_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        claim = self._receipt_claim_from_payload(payload)
        try:
            if claim.platform == Platform.YOOKASSA:
                self._verify_yookassa_claim(claim)
            else:
                self.receipt_verifier.verify(claim)
            subscription = self.repository.activate_subscription(claim)
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": str(exc)}) from exc
        token = self.token_service.issue(subscription.user_id)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": subscription.expires_at.isoformat(),
        }

    def create_yookassa_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        device_id = str(payload.get("device_id", "")).strip()
        product_id = str(payload.get("product_id", "vpn.monthly")).strip() or "vpn.monthly"
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "device_id is required"})
        try:
            payment = self.yookassa_provider.create_payment(device_id=device_id, product_id=product_id)
        except YooKassaError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc
        return {
            "provider": "yookassa",
            "payment_id": payment.id,
            "status": payment.status,
            "paid": payment.paid,
            "confirmation_url": payment.confirmation_url,
        }

    def yookassa_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = str(payload.get("event", ""))
        raw_object = payload.get("object")
        payment_object = raw_object if isinstance(raw_object, dict) else {}
        payment_id = str(payment_object.get("id", "")).strip()
        if event != "payment.succeeded" or not payment_id:
            return {"status": "ignored"}
        try:
            current_payment = self.yookassa_provider.fetch_payment(payment_id)
        except YooKassaError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc
        if str(current_payment.get("status", "")) != "succeeded" or not bool(current_payment.get("paid", False)):
            return {"status": "ignored"}
        metadata = current_payment.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        device_id = str(metadata.get("device_id", "")).strip()
        product_id = str(metadata.get("product_id", "vpn.monthly")).strip() or "vpn.monthly"
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "payment metadata.device_id is required"})
        commercial_subscription = self.repository.get_commercial_subscription(device_id)
        if commercial_subscription is not None:
            tariff = self.tariffs_by_id.get(product_id) or self.tariffs_by_id.get(commercial_subscription.tariff_id)
            if tariff is None:
                raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "unknown tariff_id"})
            activated = self.repository.activate_commercial_subscription(device_id, tariff.duration_days, payment_id)
            if activated is None:
                raise ApiError(HTTPStatus.NOT_FOUND, {"error": "subscription not found"})
            self._provision_xui_client(device_id)
            return {
                "status": "activated",
                "connect_url": f"{self.public_base_url}/connect/{device_id}",
                "expires_at": activated.expires_at.isoformat() if activated.expires_at else None,
            }
        subscription = self.repository.activate_subscription(
            ReceiptClaim(
                platform=Platform.YOOKASSA,
                receipt=payment_id,
                device_id=device_id,
                product_id=product_id,
            )
        )
        return {
            "status": "activated",
            "user_id": subscription.user_id,
            "expires_at": subscription.expires_at.isoformat(),
        }

    def freekassa_notify(self, payload: dict[str, Any]) -> str:
        """Records an incoming FreeKassa notification for manual review.

        Deliberately does NOT verify the signature or activate anything yet —
        we don't have FreeKassa's notification signing scheme confirmed.
        Orders created via freekassa_pay_redirect_url's real orders/create
        call DO carry a matchable token (payment_id=token, echoed back as
        MERCHANT_ORDER_ID), so a verified auto-activation path is buildable
        later — e.g. treating this notify as a hint and confirming status via
        FreeKassa's authoritative signed GET /orders rather than trusting
        this POST's own signature. Until that's built, trusting an
        unverified POST to grant access would let anyone "pay" for free, so
        this stays a no-op. Visible in /admin/orders audit log for manual
        activation in the meantime.
        """
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="freekassa.notify_received",
                target_type="freekassa_payment",
                target_id=str(payload.get("MERCHANT_ORDER_ID") or payload.get("intid") or "unknown"),
                result="unverified",
                details={k: str(v) for k, v in payload.items()},
            )
        )
        return "YES"

    def nodes(self, user_id: str) -> dict[str, Any]:
        self._require_known_user(user_id)
        return {"nodes": [_public_node(node) for node in choose_preferred_nodes(self.repository.list_nodes())]}

    def me(self, user_id: str) -> dict[str, Any]:
        self._require_known_user(user_id)
        subscription = self.repository.get_active_subscription(user_id)
        return {
            "user_id": user_id,
            "subscription": _public_subscription(subscription) if subscription else None,
        }

    def export_me(self, user_id: str) -> dict[str, Any]:
        exported = self.repository.export_user_data(user_id)
        if exported is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "unknown user"})
        return {"data": exported}

    def delete_me(self, user_id: str) -> dict[str, Any]:
        if not self.repository.delete_user(user_id):
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "unknown user"})
        return {"deleted": True}

    def admin_nodes(self, admin_token: str) -> dict[str, Any]:
        self._require_admin(admin_token)
        return {"nodes": [_admin_node(node) for node in self.repository.list_nodes()]}

    def admin_audit_events(self, admin_token: str) -> dict[str, Any]:
        self._require_admin(admin_token)
        return {"events": [_admin_audit_event(event) for event in self.repository.list_admin_audit_events()]}

    def admin_update_node_health(self, admin_token: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_admin(admin_token)
        health_score = self._health_score_from_payload(payload)
        status = self._node_status_from_payload(payload)
        latency_ms = self._latency_from_payload(payload)
        success_rate = self._success_rate_from_payload(payload)
        health = self._health_from_payload(payload)
        node = self.repository.update_node_health(
            node_id,
            health_score=health_score,
            status=status,
            latency_ms=latency_ms,
            success_rate=success_rate,
            health=health,
            last_check_at=datetime.now(timezone.utc),
        )
        if node is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "node not found"})
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="node.health.update",
                target_type="node",
                target_id=node_id,
                result="success",
                details=_admin_health_update_details(
                    health_score=health_score,
                    status=status,
                    latency_ms=latency_ms,
                    success_rate=success_rate,
                    health=health,
                ),
            )
        )
        return {"node": _admin_node(node)}

    def admin_upsert_node(self, admin_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_admin(admin_token)
        node = _node_from_payload(payload)
        self.repository.upsert_node(node)
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="node.upsert",
                target_type="node",
                target_id=node.id,
                result="success",
                details={"host": node.host, "port": node.port, "protocol": node.protocol.value},
            )
        )
        return {"node": _admin_node(node)}

    def admin_disable_node(self, admin_token: str, node_id: str) -> dict[str, Any]:
        self._require_admin(admin_token)
        from dataclasses import replace
        from app.domain.models import NodeHealth, NodeStatus
        node = self.repository.get_node(node_id)
        if node is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "node not found"})
        disabled = replace(node, status=NodeStatus.DISABLED, health=NodeHealth.DISABLED)
        self.repository.upsert_node(disabled)
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="node.disable",
                target_type="node",
                target_id=node_id,
                result="success",
                details={},
            )
        )
        return {"node": _admin_node(disabled)}

    def config(self, user_id: str) -> dict[str, Any]:
        self._require_known_user(user_id)
        if self.repository.get_active_subscription(user_id) is None:
            raise ApiError(HTTPStatus.FORBIDDEN, {"error": "active subscription required"})
        try:
            config = self.config_builder.build_client_config(choose_preferred_nodes(self.repository.list_nodes()))
            validate_config_shape(config)
            return config
        except (ValueError, ConfigValidationError) as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc

    def user_id_from_authorization(self, authorization: str) -> str:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "bearer token required"})
        try:
            claims = self.token_service.verify(token)
        except TokenError as exc:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": str(exc)}) from exc
        self._require_known_user(claims.subject)
        return claims.subject

    def _commercial_subscription(self, token: str) -> Any:
        subscription = self.repository.get_commercial_subscription(token)
        if subscription is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "subscription not found"})
        return subscription

    def _require_active_commercial_subscription(self, token: str) -> None:
        subscription = self._commercial_subscription(token)
        if not subscription.is_active():
            raise ApiError(HTTPStatus.FORBIDDEN, {"error": "subscription expired"})

    def _tariff_from_payload(self, payload: dict[str, Any]) -> Tariff:
        tariff_id = str(payload.get("tariff_id", "")).strip()
        tariff = self.tariffs_by_id.get(tariff_id)
        if tariff is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "unknown tariff_id"})
        return tariff

    def _require_admin(self, admin_token: str) -> None:
        if not self.admin_token or not hmac.compare_digest(admin_token, self.admin_token):
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "admin token required"})

    def _health_score_from_payload(self, payload: dict[str, Any]) -> int:
        try:
            health_score = int(payload.get("health_score"))
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "health_score must be an integer"}) from exc
        if not 0 <= health_score <= 100:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "health_score must be between 0 and 100"})
        return health_score

    def _node_status_from_payload(self, payload: dict[str, Any]) -> NodeStatus | None:
        raw_status = payload.get("status")
        if raw_status is None:
            return None
        try:
            return NodeStatus(str(raw_status))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "status must be active, draining, or disabled"}) from exc

    def _latency_from_payload(self, payload: dict[str, Any]) -> int | None:
        raw_latency = payload.get("latency_ms")
        if raw_latency is None:
            return None
        try:
            latency_ms = int(raw_latency)
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "latency_ms must be an integer"}) from exc
        if latency_ms < 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "latency_ms must be positive"})
        return latency_ms

    def _success_rate_from_payload(self, payload: dict[str, Any]) -> float | None:
        raw_success_rate = payload.get("success_rate")
        if raw_success_rate is None:
            return None
        try:
            success_rate = float(raw_success_rate)
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "success_rate must be a number"}) from exc
        if not 0 <= success_rate <= 1:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "success_rate must be between 0 and 1"})
        return success_rate

    def _health_from_payload(self, payload: dict[str, Any]) -> NodeHealth | None:
        raw_health = payload.get("health")
        if raw_health is None:
            return None
        try:
            return NodeHealth(str(raw_health))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "health must be healthy, degraded, or disabled"}) from exc

    def _receipt_claim_from_payload(self, payload: dict[str, Any]) -> ReceiptClaim:
        try:
            platform = Platform(str(payload.get("platform", "")).lower())
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "platform must be apple, google, yookassa, or sandbox"}) from exc

        receipt = str(payload.get("receipt", "")).strip()
        device_id = str(payload.get("device_id", "")).strip()
        product_id = str(payload.get("product_id", "vpn.monthly")).strip() or "vpn.monthly"
        if not receipt:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "receipt is required"})
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "device_id is required"})
        return ReceiptClaim(platform=platform, receipt=receipt, device_id=device_id, product_id=product_id)

    def _require_known_user(self, user_id: str) -> None:
        if self.repository.get_user(user_id) is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "unknown user"})

    def _verify_yookassa_claim(self, claim: ReceiptClaim) -> None:
        try:
            payment = self.yookassa_provider.fetch_payment(claim.receipt)
        except YooKassaError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc
        if str(payment.get("status", "")) != "succeeded" or not bool(payment.get("paid", False)):
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "yookassa payment is not paid"})
        metadata = payment.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if str(metadata.get("device_id", "")).strip() != claim.device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "yookassa payment device mismatch"})
        if str(metadata.get("product_id", "")).strip() != claim.product_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "yookassa payment product mismatch"})


def _public_node(node: Any) -> dict[str, Any]:
    return {
        "id": node.id,
        "region": node.region,
        "provider": node.provider,
        "country_code": node.country_code,
        "protocol": node.protocol.value,
        "status": node.status.value,
        "health": node.health.value,
        "health_score": node.health_score,
        "latency_ms": node.latency_ms,
        "success_rate": node.success_rate,
        "priority": node.priority,
        "score": round(node_score(node), 2),
    }


def _public_subscription(subscription: Any) -> dict[str, Any]:
    return {
        "active": subscription.is_active(),
        "platform": subscription.platform.value,
        "product_id": subscription.product_id,
        "expires_at": subscription.expires_at.isoformat(),
    }


def _admin_node(node: Any) -> dict[str, Any]:
    return {
        **_public_node(node),
        "tag": node.tag,
        "host": node.host,
        "port": node.port,
        "weight": node.weight,
        "last_check_at": node.last_check_at.isoformat() if node.last_check_at else None,
        "usable": node.is_usable(),
    }


def _admin_order(subscription: Any) -> dict[str, str]:
    if subscription.is_active():
        status = "active"
    elif subscription.status == "pending":
        status = "pending"
    else:
        status = "expired"
    payment = ""
    if subscription.pay_amount and subscription.pay_coin_id:
        payment = f"{subscription.pay_amount} {subscription.pay_coin_id}"
    return {
        "token": subscription.token,
        "order_ref": subscription.token[:12].upper(),
        "tariff_id": subscription.tariff_id,
        "status": status,
        "created_at": subscription.created_at.strftime("%d.%m.%Y %H:%M"),
        "expires_at": subscription.expires_at.strftime("%d.%m.%Y") if subscription.expires_at else "—",
        "payment": payment,
        "paid_tx": subscription.paid_tx or "",
        "payer": subscription.payer or "",
        "email": subscription.customer_email or "",
        "tg": "✓" if subscription.tg_chat_id else "",
        "connect_url": f"/connect/{subscription.token}",
    }


def _admin_audit_event(event: AdminAuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "occurred_at": event.occurred_at.isoformat(),
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "result": event.result,
        "details": event.details,
    }


def _admin_health_update_details(
    health_score: int,
    status: NodeStatus | None,
    latency_ms: int | None,
    success_rate: float | None,
    health: NodeHealth | None,
) -> dict[str, Any]:
    details: dict[str, Any] = {"health_score": health_score}
    if status is not None:
        details["status"] = status.value
    if latency_ms is not None:
        details["latency_ms"] = latency_ms
    if success_rate is not None:
        details["success_rate"] = success_rate
    if health is not None:
        details["health"] = health.value
    return details


def _metric_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _repository_backend_name(repository: Repository) -> str:
    name = type(repository).__name__.lower()
    if "sqlite" in name:
        return "sqlite"
    if "memory" in name:
        return "memory"
    return "custom"


def _mask_token(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def _rub_to_usdt(price_rub: str, rate_rub: str) -> str:
    rub = Decimal(price_rub)
    rate = Decimal(rate_rub)
    usdt = (rub / rate).quantize(Decimal("0.01"), rounding=ROUND_UP)
    return str(usdt)


def _node_from_payload(payload: dict[str, Any]) -> VpnNode:
    node_id = str(payload.get("id", "")).strip()
    if not node_id:
        raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "id is required"})
    host = str(payload.get("host", "")).strip()
    if not host:
        raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "host is required"})
    try:
        port = int(payload.get("port", 443))
    except (TypeError, ValueError) as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "port must be an integer"}) from exc
    if not 1 <= port <= 65535:
        raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "port must be between 1 and 65535"})

    protocol_raw = str(payload.get("protocol", "vless")).strip().lower()
    try:
        protocol = Protocol(protocol_raw)
    except ValueError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, {"error": f"unknown protocol: {protocol_raw}"}) from exc

    status_raw = str(payload.get("status", "active")).strip().lower()
    try:
        status = NodeStatus(status_raw)
    except ValueError:
        status = NodeStatus.ACTIVE

    health_raw = str(payload.get("health", "healthy")).strip().lower()
    try:
        health = NodeHealth(health_raw)
    except ValueError:
        health = NodeHealth.HEALTHY

    priority = int(payload.get("priority", 50))
    region = str(payload.get("region", "unknown")).strip()
    country_code = str(payload.get("country_code", "XX")).strip()
    provider = str(payload.get("provider", "manual")).strip()

    options: VlessOptions | None = None
    if protocol == Protocol.VLESS:
        opts = payload.get("options") or {}
        uuid = str(opts.get("uuid", "")).strip()
        sni = str(opts.get("server_name", "")).strip()
        public_key = str(opts.get("public_key", "")).strip()
        short_id = str(opts.get("short_id", "")).strip()
        if not uuid:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "options.uuid is required for VLESS"})
        if not public_key:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "options.public_key is required for VLESS"})
        if not short_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "options.short_id is required for VLESS"})
        if not sni:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "options.server_name (SNI) is required for VLESS"})
        options = VlessOptions(
            uuid=uuid,
            server_name=sni,
            public_key=public_key,
            short_id=short_id,
            flow=str(opts.get("flow", "xtls-rprx-vision")).strip() or None,
            fingerprint=str(opts.get("fingerprint", "chrome")).strip() or "chrome",
            label=str(opts.get("label", f"Node {node_id}")).strip() or None,
        )

    return VpnNode(
        id=node_id,
        tag=str(payload.get("tag", node_id)).strip(),
        region=region,
        provider=provider,
        country_code=country_code,
        host=host,
        port=port,
        protocol=protocol,
        status=status,
        health=health,
        priority=priority,
        options=options,
    )


def _build_coin_options(
    price_rub: str,
    wallets: dict[str, str],
    rate_svc: ExchangeRateService,
) -> list[dict[str, Any]]:
    """Return list of {id, label, network_label, amount, address, color} for configured coins.

    Distinct networks legitimately share one wallet_key (e.g. ERC20 and BEP20
    both settle to the same EVM address), so dedup is keyed on coin.id, not on
    (wallet_key, coingecko_id) — that pair would otherwise hide every network
    past the first for a coin whose networks share an address.
    """
    result: list[dict[str, Any]] = []
    for coin in ALL_COINS:
        addr = wallets.get(coin.wallet_key)
        if not addr:
            continue
        amount = rate_svc.coin_amount(price_rub, coin) or "—"
        result.append({
            "id": coin.id,
            "label": coin.label,
            "network_label": coin.network_label,
            "amount": amount,
            "address": addr,
            "color": coin.color,
            # Lets the page build the transfer for the buyer's wallet
            # instead of making them retype address and amount by hand.
            "pay": transfer_spec(coin.id),
            "pay_uri": payment_uri(coin.id, addr, amount),
            "pay_units": payment_units(coin.id, amount),
            "wallets": wallet_links(coin.id, addr, amount),
        })
    return result
