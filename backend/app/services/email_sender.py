from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.domain.models import CommercialSubscription


class EmailSender:
    """Send the subscription link to the customer's email on activation.

    Best-effort: SMTP failures are logged and swallowed so that payment
    activation never depends on the mail server.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_address: str,
        public_base_url: str,
        timeout_seconds: int = 20,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_address = from_address
        self.public_base_url = public_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def on_activated(self, subscription: CommercialSubscription) -> bool:
        if not subscription.customer_email:
            return False
        message = self._build_message(subscription)
        try:
            self._send(message)
            return True
        except Exception as exc:
            print(f"email-sender error: {exc}")
            return False

    def _build_message(self, subscription: CommercialSubscription) -> EmailMessage:
        sub_url = f"{self.public_base_url}/sub/{subscription.token}"
        connect_url = f"{self.public_base_url}/connect/{subscription.token}"
        message = EmailMessage()
        message["Subject"] = "VPN активен — ваша ссылка подписки"
        message["From"] = self.from_address
        message["To"] = subscription.customer_email
        message.set_content(
            "Оплата подтверждена, VPN активен.\n\n"
            f"Ссылка подписки (вставьте в v2rayN / v2rayNG / Hiddify):\n{sub_url}\n\n"
            f"Страница вашего заказа (статус, QR-код, продление):\n{connect_url}\n\n"
            "Сохраните это письмо — по этим ссылкам вы всегда восстановите доступ."
        )
        return message

    def _send(self, message: EmailMessage) -> None:
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout_seconds) as smtp:
                smtp.login(self.user, self.password)
                smtp.send_message(message)
            return
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds) as smtp:
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.send_message(message)
