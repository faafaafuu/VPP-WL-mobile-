from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from app.domain.models import CommercialSubscription
from app.repositories.factory import Repository


class TelegramError(Exception):
    pass


class TelegramTransport(Protocol):
    def call(self, method: str, params: dict[str, Any]) -> Any:
        ...


class HttpTelegramTransport:
    """Thin urllib client for the Telegram Bot API (stdlib only)."""

    def __init__(self, bot_token: str, timeout_seconds: int = 40) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.timeout_seconds = timeout_seconds

    def call(self, method: str, params: dict[str, Any]) -> Any:
        body = json.dumps(params).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise TelegramError(f"telegram {method} failed: {exc}") from exc
        if not payload.get("ok"):
            raise TelegramError(f"telegram {method} error: {payload.get('description')}")
        return payload.get("result")


class TelegramBot:
    """Binds orders to Telegram chats and hands out subscription links.

    /start <order-token> — bind the order to this chat and reply with its state.
    Any other message — list the orders already bound to this chat.
    """

    def __init__(
        self,
        transport: TelegramTransport,
        repository: Repository,
        public_base_url: str,
    ) -> None:
        self.transport = transport
        self.repository = repository
        self.public_base_url = public_base_url.rstrip("/")

    def get_username(self) -> str:
        me = self.transport.call("getMe", {})
        return str(me.get("username", ""))

    def get_updates(self, offset: int, poll_timeout: int = 25) -> list[dict[str, Any]]:
        result = self.transport.call(
            "getUpdates",
            {"offset": offset, "timeout": poll_timeout, "allowed_updates": ["message"]},
        )
        return list(result or [])

    def send(
        self,
        chat_id: str,
        text: str,
        keyboard: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if keyboard:
            params["reply_markup"] = {"inline_keyboard": keyboard}
        self.transport.call("sendMessage", params)

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", "")).strip()
        text = str(message.get("text") or "").strip()
        if not chat_id or not text:
            return
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""
            if token:
                self._bind(chat_id, token)
                return
        self._send_bound_orders(chat_id)

    def notify_activated(self, subscription: CommercialSubscription) -> bool:
        if not subscription.tg_chat_id:
            return False
        try:
            self.send(
                subscription.tg_chat_id,
                "✅ <b>Оплата подтверждена — VPN активен"
                + (f" до {subscription.expires_at.strftime('%d.%m.%Y')}" if subscription.expires_at else "")
                + "!</b>\n\nНажмите кнопку — ссылка скопируется. Вставьте её в v2rayN / v2rayNG / Hiddify "
                "как подписку (subscription).",
                keyboard=self._active_keyboard(subscription),
            )
            return True
        except TelegramError:
            return False

    def _bind(self, chat_id: str, token: str) -> None:
        subscription = self.repository.bind_telegram(token, chat_id)
        if subscription is None:
            self.send(chat_id, "Заказ не найден. Откройте ссылку «привязать Telegram» на странице заказа ещё раз.")
            return
        if subscription.is_active():
            self.send(
                chat_id,
                "🔗 <b>Заказ привязан — VPN активен!</b>\n\n"
                "Нажмите кнопку — ссылка скопируется. Вставьте её в v2rayN / v2rayNG / Hiddify.",
                keyboard=self._active_keyboard(subscription),
            )
        elif subscription.status == "pending":
            self.send(
                chat_id,
                "🔗 <b>Заказ привязан к этому чату.</b>\n"
                "⏳ Ожидаем оплату — как только сеть подтвердит перевод, пришлю ссылку сюда.",
                keyboard=[
                    [{"text": "💳 Перейти к оплате", "url": self._invoice_url(subscription)}],
                    [{"text": "📄 Страница заказа", "url": self._connect_url(subscription)}],
                ],
            )
        else:
            self.send(
                chat_id,
                "🔗 Заказ привязан, но подписка истекла.",
                keyboard=[[{"text": "🔄 Продлить доступ", "url": self._connect_url(subscription)}]],
            )

    def _send_bound_orders(self, chat_id: str) -> None:
        subscriptions = self.repository.list_commercial_subscriptions_by_telegram(chat_id)
        if not subscriptions:
            self.send(
                chat_id,
                "У этого чата пока нет привязанных заказов.\n"
                f"Оформите доступ на {self.public_base_url} и нажмите «привязать Telegram» на странице заказа.",
            )
            return
        for subscription in sorted(subscriptions, key=lambda item: item.created_at, reverse=True):
            ref = subscription.token[:12].upper()
            if subscription.is_active():
                expires = subscription.expires_at.strftime("%d.%m.%Y")
                self.send(
                    chat_id,
                    f"✅ Заказ <code>{ref}</code> — активен до {expires}.",
                    keyboard=self._active_keyboard(subscription),
                )
            elif subscription.status == "pending":
                self.send(
                    chat_id,
                    f"⏳ Заказ <code>{ref}</code> — ждёт оплату.",
                    keyboard=[
                        [{"text": "💳 Перейти к оплате", "url": self._invoice_url(subscription)}],
                        [{"text": "📄 Страница заказа", "url": self._connect_url(subscription)}],
                    ],
                )
            else:
                self.send(
                    chat_id,
                    f"❌ Заказ <code>{ref}</code> — подписка истекла.",
                    keyboard=[[{"text": "🔄 Продлить доступ", "url": self._connect_url(subscription)}]],
                )

    def _active_keyboard(self, subscription: CommercialSubscription) -> list[list[dict[str, Any]]]:
        return [
            [{"text": "📋 Скопировать ссылку подписки", "copy_text": {"text": self._sub_url(subscription)}}],
            [{"text": "📄 Страница заказа · QR · инструкция", "url": self._connect_url(subscription)}],
        ]

    def _sub_url(self, subscription: CommercialSubscription) -> str:
        return f"{self.public_base_url}/sub/{subscription.token}"

    def _connect_url(self, subscription: CommercialSubscription) -> str:
        return f"{self.public_base_url}/connect/{subscription.token}"

    def _invoice_url(self, subscription: CommercialSubscription) -> str:
        return f"{self.public_base_url}/invoice/{subscription.token}"


def telegram_deep_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={urllib.parse.quote(token, safe='')}"
