from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Protocol

from app.domain.models import CommercialSubscription
from app.domain.tariffs import Tariff
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


_COMMANDS = [
    {"command": "status", "description": "Мои заказы и срок действия VPN"},
    {"command": "help", "description": "Как пользоваться ботом"},
]

_HELP_TEXT = (
    "🤖 <b>VPN Router — бот</b>\n\n"
    "Здесь можно посмотреть статус оплаченного доступа и быстро получить ссылку подключения.\n\n"
    "• Купить доступ и привязать заказ к этому чату — со страницы заказа на сайте, кнопка «привязать Telegram».\n"
    "• /status — список ваших заказов: активен ли, сколько дней осталось, лимиты.\n"
    "• Авторизация не нужна для покупки — она нужна только чтобы потом посмотреть статус здесь."
)


class TelegramBot:
    """Binds orders to Telegram chats and hands out subscription links.

    /start <order-token> — bind the order to this chat and reply with its state.
    /status (or any other message) — list the orders already bound to this chat.
    /help — usage instructions.
    """

    def __init__(
        self,
        transport: TelegramTransport,
        repository: Repository,
        public_base_url: str,
        tariffs_by_id: dict[str, Tariff] | None = None,
    ) -> None:
        self.transport = transport
        self.repository = repository
        self.public_base_url = public_base_url.rstrip("/")
        self.tariffs_by_id = tariffs_by_id or {}

    def get_username(self) -> str:
        me = self.transport.call("getMe", {})
        return str(me.get("username", ""))

    def set_commands(self) -> None:
        """Registers the / command menu Telegram shows next to the message box."""
        self.transport.call("setMyCommands", {"commands": _COMMANDS})

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
        if text.startswith("/help"):
            self.send(chat_id, _HELP_TEXT)
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
                + "!</b>\n\n"
                + self._limits_line(subscription)
                + "\n\nНажмите кнопку — ссылка скопируется. Вставьте её в v2rayN / v2rayNG / Hiddify "
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
                + self._limits_line(subscription)
                + "\n\nНажмите кнопку — ссылка скопируется. Вставьте её в v2rayN / v2rayNG / Hiddify.",
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
                f"Оформите доступ на {self.public_base_url} и нажмите «привязать Telegram» на странице заказа.\n\n"
                "/help — что умеет этот бот",
            )
            return
        for subscription in sorted(subscriptions, key=lambda item: item.created_at, reverse=True):
            ref = subscription.token[:12].upper()
            tariff_title = self._tariff_title(subscription)
            if subscription.is_active():
                expires = subscription.expires_at.strftime("%d.%m.%Y")
                days_left = self._days_left(subscription)
                self.send(
                    chat_id,
                    f"✅ <b>{ref}</b>{tariff_title}\n"
                    f"Активен ещё {days_left} (до {expires})\n"
                    f"{self._limits_line(subscription)}",
                    keyboard=self._active_keyboard(subscription),
                )
            elif subscription.status == "pending":
                self.send(
                    chat_id,
                    f"⏳ <b>{ref}</b>{tariff_title}\nЖдём оплату.",
                    keyboard=[
                        [{"text": "💳 Перейти к оплате", "url": self._invoice_url(subscription)}],
                        [{"text": "📄 Страница заказа", "url": self._connect_url(subscription)}],
                    ],
                )
            else:
                self.send(
                    chat_id,
                    f"❌ <b>{ref}</b>{tariff_title}\nПодписка истекла.",
                    keyboard=[[{"text": "🔄 Продлить доступ", "url": self._connect_url(subscription)}]],
                )

    def _active_keyboard(self, subscription: CommercialSubscription) -> list[list[dict[str, Any]]]:
        return [
            [{"text": "📋 Скопировать ссылку подписки", "copy_text": {"text": self._sub_url(subscription)}}],
            [{"text": "📄 Страница заказа · QR · инструкция", "url": self._connect_url(subscription)}],
        ]

    def _tariff_title(self, subscription: CommercialSubscription) -> str:
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        return f" — {tariff.title}" if tariff else ""

    def _limits_line(self, subscription: CommercialSubscription) -> str:
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        if tariff is None:
            return ""
        traffic = f"{tariff.traffic_gb} ГБ" if tariff.traffic_gb else "безлимит"
        return f"До {tariff.max_devices} устройств · {traffic} трафика"

    def _days_left(self, subscription: CommercialSubscription) -> str:
        if subscription.expires_at is None:
            return "0 дней"
        remaining = (subscription.expires_at - datetime.now(timezone.utc)).days
        remaining = max(remaining, 0)
        last_digit = remaining % 10
        last_two = remaining % 100
        if 11 <= last_two <= 14:
            word = "дней"
        elif last_digit == 1:
            word = "день"
        elif 2 <= last_digit <= 4:
            word = "дня"
        else:
            word = "дней"
        return f"{remaining} {word}"

    def _sub_url(self, subscription: CommercialSubscription) -> str:
        return f"{self.public_base_url}/sub/{subscription.token}"

    def _connect_url(self, subscription: CommercialSubscription) -> str:
        return f"{self.public_base_url}/connect/{subscription.token}"

    def _invoice_url(self, subscription: CommercialSubscription) -> str:
        return f"{self.public_base_url}/invoice/{subscription.token}"


def telegram_deep_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={urllib.parse.quote(token, safe='')}"
