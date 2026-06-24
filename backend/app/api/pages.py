from __future__ import annotations

from html import escape

from app.domain.models import CommercialSubscription
from app.domain.tariffs import Tariff


def landing_page(tariffs: tuple[Tariff, ...]) -> str:
    cards = "\n".join(_tariff_card(tariff) for tariff in tariffs)
    return _page(
        "Быстрый VPN-доступ",
        f"""
        <main class="shell hero">
          <section class="hero-copy">
            <p class="eyebrow">VPN Router</p>
            <h1>Быстрый VPN-доступ</h1>
            <p class="lead">Работает с YouTube, Telegram, Instagram, ChatGPT и сайтами. Подключение за 1 минуту, без установки нашего приложения.</p>
            <a class="primary-link" href="#pricing">Выбрать тариф</a>
          </section>
          <section id="pricing" class="pricing" aria-label="Тарифы">
            {cards}
          </section>
          <section class="notes">
            <span>Без сложной настройки</span>
            <span>Готовые клиенты: v2rayN, v2rayNG, Hiddify, Streisand</span>
            <span>Ссылка подключения сразу после оплаты</span>
          </section>
        </main>
        """,
    )


def connect_page(
    subscription: CommercialSubscription,
    subscription_url: str,
    tariffs: tuple[Tariff, ...],
) -> str:
    if subscription.is_active():
        expires = subscription.expires_at.strftime("%d.%m.%Y") if subscription.expires_at else ""
        status = f"""
          <div class="status-card active">
            <p class="eyebrow">Подписка</p>
            <h1>Ваш VPN активен</h1>
            <p class="lead compact">Действует до {escape(expires)}. Нажмите подключить или импортируйте ссылку в клиент.</p>
            <div class="actions">
              <button class="button primary" type="button" onclick="connectClient()">Подключить</button>
              <button class="button" type="button" onclick="copySub()">Скопировать ссылку</button>
              <button class="button" type="button" onclick="toggleQr()">Показать QR</button>
            </div>
            <p class="sub-url" id="subUrl">{escape(subscription_url)}</p>
            <p class="hint" id="connectHint" hidden>Если клиент не открылся, скопируйте ссылку или отсканируйте QR.</p>
            <div class="qr-wrap" id="qrWrap" hidden><img src="/sub/{escape(subscription.token)}/qr" alt="QR код подписки"></div>
          </div>
        """
    else:
        status = f"""
          <div class="status-card expired">
            <p class="eyebrow">Подписка</p>
            <h1>Подписка закончилась</h1>
            <p class="lead compact">Продлите доступ, и ссылка снова заработает автоматически.</p>
            <a class="primary-link" href="/">Продлить</a>
          </div>
        """
    return _page(
        "Подключение VPN",
        f"""
        <main class="shell connect">
          {status}
          <section class="instructions">
            <details open>
              <summary>iPhone / Hiddify / Streisand / Shadowrocket</summary>
              <ol><li>Установите клиент из App Store.</li><li>Нажмите “Подключить”.</li><li>Если не открылось, отсканируйте QR или вставьте ссылку.</li></ol>
            </details>
            <details>
              <summary>Android / Hiddify</summary>
              <ol><li>Установите Hiddify.</li><li>Нажмите “Подключить” или вставьте ссылку подписки.</li></ol>
            </details>
            <details>
              <summary>Android / v2rayNG</summary>
              <ol><li>Установите v2rayNG.</li><li>Нажмите “Скопировать ссылку”.</li><li>Добавьте subscription URL.</li></ol>
            </details>
            <details>
              <summary>Windows / v2rayN</summary>
              <ol><li>Установите v2rayN.</li><li>Нажмите “Скопировать ссылку”.</li><li>Subscriptions → Add subscription.</li><li>Вставьте ссылку и нажмите Update subscription.</li></ol>
            </details>
          </section>
          <section class="pricing compact-pricing">
            <h2>Продлить доступ</h2>
            {''.join(_tariff_card(tariff, compact=True) for tariff in tariffs)}
          </section>
        </main>
        <script>
          const subUrl = {subscription_url!r};
          async function copySub() {{
            await navigator.clipboard.writeText(subUrl);
            const hint = document.getElementById('connectHint');
            hint.hidden = false;
            hint.textContent = 'Ссылка скопирована. Вставьте её в ваш VPN-клиент.';
          }}
          function toggleQr() {{
            const wrap = document.getElementById('qrWrap');
            wrap.hidden = !wrap.hidden;
          }}
          function connectClient() {{
            const hint = document.getElementById('connectHint');
            hint.hidden = false;
            hint.textContent = 'Если клиент не открылся, скопируйте ссылку или отсканируйте QR.';
            toggleQr();
          }}
        </script>
        """,
    )


def invoice_page(
    subscription: CommercialSubscription,
    tariff: Tariff,
    usdt_trc20_address: str,
    amount_usdt: str,
) -> str:
    order_ref = subscription.token[:12].upper()
    price_rub = _price(tariff.price_rub)
    return _page(
        "Оплата криптовалютой",
        f"""
        <main class="shell connect">
          <div class="status-card active" style="background:linear-gradient(145deg,rgba(103,247,165,.13),rgba(255,255,255,.08))">
            <p class="eyebrow">Оплата</p>
            <h1>{escape(tariff.title)}</h1>
            <p class="lead compact">Переведите <strong>{escape(amount_usdt)} USDT TRC20</strong> на адрес ниже.<br>
            Стоимость тарифа: {escape(price_rub)}. Номер заказа: <code>{escape(order_ref)}</code></p>
            <div class="crypto-card">
              <p class="crypto-label">USDT TRC20 адрес</p>
              <p class="crypto-addr" id="walletAddr">{escape(usdt_trc20_address)}</p>
              <div class="actions">
                <button class="button primary" type="button" onclick="copyAddr()">Скопировать адрес</button>
                <button class="button" type="button" onclick="toggleAddrQr()">QR-код адреса</button>
              </div>
              <div class="qr-wrap" id="addrQr" hidden>
                <img src="/invoice/{escape(subscription.token)}/qr" alt="QR адреса кошелька">
              </div>
              <p class="hint" id="copyHint" hidden>Адрес скопирован.</p>
            </div>
            <div class="instructions" style="margin-top:18px">
              <details open>
                <summary>Как оплатить</summary>
                <ol>
                  <li>Откройте ваш крипто-кошелёк (Binance, OKX, Trust Wallet, Bybit и др.).</li>
                  <li>Выберите сеть <strong>TRC20 (Tron)</strong>.</li>
                  <li>Переведите ровно <strong>{escape(amount_usdt)} USDT</strong>.</li>
                  <li>В комментарии/мемо укажите номер заказа: <strong>{escape(order_ref)}</strong>.</li>
                  <li>После подтверждения транзакции администратор активирует доступ — обычно в течение 30 минут.</li>
                </ol>
              </details>
            </div>
            <div style="margin-top:20px">
              <a class="button" href="/connect/{escape(subscription.token)}">Проверить статус доступа</a>
            </div>
          </div>
        </main>
        <script>
          const walletAddr = {usdt_trc20_address!r};
          async function copyAddr() {{
            await navigator.clipboard.writeText(walletAddr);
            const hint = document.getElementById('copyHint');
            hint.hidden = false;
          }}
          function toggleAddrQr() {{
            const qr = document.getElementById('addrQr');
            qr.hidden = !qr.hidden;
          }}
        </script>
        <style>
          .crypto-card {{ margin-top: 18px; border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: rgba(0,0,0,.22); }}
          .crypto-label {{ margin: 0 0 6px; color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .1em; }}
          .crypto-addr {{ margin: 0 0 14px; font-family: monospace; font-size: .92rem; word-break: break-all; color: var(--cyan); }}
          code {{ font-family: monospace; color: var(--cyan); }}
        </style>
        """,
    )


def not_found_page() -> str:
    return _page(
        "Ссылка не найдена",
        """
        <main class="shell connect">
          <div class="status-card expired">
            <p class="eyebrow">Ошибка</p>
            <h1>Ссылка не найдена</h1>
            <p class="lead compact">Проверьте адрес или оформите новый доступ.</p>
            <a class="primary-link" href="/">Выбрать тариф</a>
          </div>
        </main>
        """,
    )


def _tariff_card(tariff: Tariff, compact: bool = False) -> str:
    badge = f'<span class="badge">{escape(tariff.badge)}</span>' if tariff.badge else ""
    css = "tariff compact" if compact else "tariff"
    return f"""
      <form class="{css}" method="post" action="/checkout">
        {badge}
        <input type="hidden" name="tariff_id" value="{escape(tariff.id)}">
        <h2>{escape(tariff.title)}</h2>
        <p class="price">{escape(_price(tariff.price_rub))}</p>
        <p>Выберите тариф и получите ссылку подключения.</p>
        <button class="button primary" type="submit">Оплатить</button>
      </form>
    """


def _price(raw: str) -> str:
    if raw.endswith(".00"):
        raw = raw[:-3]
    return f"{raw} ₽"


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #05070d;
      --text: #f7fbff;
      --muted: #a9b6c7;
      --line: rgba(255,255,255,.14);
      --panel: rgba(255,255,255,.08);
      --panel-strong: rgba(255,255,255,.13);
      --cyan: #36e7ff;
      --green: #67f7a5;
      --pink: #ff5fd7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 18% 10%, rgba(54,231,255,.22), transparent 31rem),
        radial-gradient(circle at 88% 18%, rgba(255,95,215,.20), transparent 28rem),
        linear-gradient(145deg, #05070d 0%, #0d1322 54%, #060914 100%);
      color: var(--text);
    }}
    a {{ color: inherit; }}
    .shell {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; }}
    .hero {{ min-height: 100vh; display: grid; gap: 28px; align-content: center; padding: 42px 0; }}
    .connect {{ padding: 28px 0 56px; }}
    .hero-copy {{ max-width: 760px; }}
    .eyebrow {{ margin: 0 0 10px; color: var(--cyan); font-size: .78rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }}
    h1 {{ margin: 0; font-size: clamp(2.5rem, 8vw, 5.8rem); line-height: .95; letter-spacing: 0; }}
    h2 {{ margin: 0; font-size: 1.25rem; letter-spacing: 0; }}
    .lead {{ max-width: 720px; margin: 18px 0 0; color: var(--muted); font-size: clamp(1.08rem, 3vw, 1.35rem); line-height: 1.55; }}
    .lead.compact {{ font-size: 1rem; }}
    .primary-link, .button {{
      display: inline-flex; align-items: center; justify-content: center; min-height: 48px; border: 1px solid var(--line);
      border-radius: 8px; padding: 0 18px; color: var(--text); background: var(--panel); text-decoration: none;
      font: inherit; font-weight: 800; cursor: pointer;
    }}
    .primary-link, .button.primary {{ border: 0; background: linear-gradient(135deg, var(--cyan), var(--green)); color: #061018; box-shadow: 0 12px 36px rgba(54,231,255,.24); }}
    .hero .primary-link {{ margin-top: 26px; }}
    .pricing {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .tariff, .status-card, .instructions details {{
      position: relative; border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
      backdrop-filter: blur(18px); box-shadow: 0 16px 50px rgba(0,0,0,.24);
    }}
    .tariff {{ padding: 20px; display: grid; gap: 12px; align-content: start; }}
    .tariff p {{ margin: 0; color: var(--muted); line-height: 1.45; }}
    .price {{ color: var(--text) !important; font-size: 2.05rem; font-weight: 900; }}
    .badge {{ position: absolute; top: 14px; right: 14px; color: #061018; background: var(--green); border-radius: 999px; padding: 5px 9px; font-size: .74rem; font-weight: 900; }}
    .notes {{ display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); }}
    .notes span {{ border: 1px solid var(--line); border-radius: 999px; padding: 9px 12px; background: rgba(255,255,255,.05); }}
    .status-card {{ margin-top: 22px; padding: 24px; overflow: hidden; }}
    .status-card.active {{ background: linear-gradient(145deg, rgba(54,231,255,.14), rgba(255,255,255,.08)); }}
    .status-card.expired {{ background: linear-gradient(145deg, rgba(255,95,95,.14), rgba(255,255,255,.08)); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }}
    .sub-url {{ overflow-wrap: anywhere; color: var(--muted); border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: rgba(0,0,0,.22); }}
    .hint {{ color: var(--green); }}
    .qr-wrap {{ width: min(320px, 100%); margin-top: 14px; padding: 12px; border-radius: 8px; background: #fff; }}
    .qr-wrap img {{ display: block; width: 100%; height: auto; }}
    .instructions {{ display: grid; gap: 10px; margin-top: 16px; }}
    summary {{ padding: 16px; cursor: pointer; font-weight: 850; }}
    ol {{ margin: 0; padding: 0 22px 18px 38px; color: var(--muted); line-height: 1.65; }}
    .compact-pricing {{ margin-top: 16px; grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .compact-pricing > h2 {{ grid-column: 1 / -1; margin-top: 12px; }}
    .tariff.compact .price {{ font-size: 1.45rem; }}
    @media (max-width: 760px) {{
      .shell {{ width: min(100% - 22px, 560px); }}
      .hero {{ min-height: auto; padding: 26px 0 38px; }}
      .pricing, .compact-pricing {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: clamp(2.45rem, 15vw, 4rem); }}
      .status-card {{ padding: 18px; }}
      .actions {{ display: grid; grid-template-columns: 1fr; }}
      .button, .primary-link {{ width: 100%; }}
    }}
  </style>
</head>
<body>{body}</body>
</html>"""
