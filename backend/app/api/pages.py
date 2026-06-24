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
            <p class="lead">Работает с YouTube, Telegram, Instagram, ChatGPT и сайтами. Берёте готовый клиент, вставляете ссылку — подключение за 1 минуту.</p>
            <a class="primary-link" href="#pricing">Выбрать тариф</a>
          </section>
          <section id="pricing" class="pricing" aria-label="Тарифы">
            {cards}
          </section>
          <section class="steps" aria-label="Как это работает">
            <div class="step"><span class="step-num">1</span><p>Оплатите тариф удобной криптовалютой</p></div>
            <div class="step"><span class="step-num">2</span><p>Установите клиент: v2rayN (ПК), v2rayNG или Hiddify (телефон)</p></div>
            <div class="step"><span class="step-num">3</span><p>После подтверждения оплаты получите ссылку и подключитесь</p></div>
          </section>
          <section class="notes">
            <span>До 3 устройств на одну подписку</span>
            <span>Основной клиент — v2rayN</span>
            <span>Без сложной настройки</span>
          </section>
        </main>
        """,
    )


def connect_page(
    subscription: CommercialSubscription,
    subscription_url: str,
    tariffs: tuple[Tariff, ...],
    configs: list[dict[str, str]] | None = None,
) -> str:
    tariff_map = {t.id: t for t in tariffs}
    current_tariff = tariff_map.get(subscription.tariff_id)
    max_devices = current_tariff.max_devices if current_tariff else 3
    if subscription.is_active():
        expires = subscription.expires_at.strftime("%d.%m.%Y") if subscription.expires_at else ""
        configs_block = _configs_block(configs or [])
        status = f"""
          <div class="status-card active">
            <p class="eyebrow">Подписка</p>
            <h1>Ваш VPN активен</h1>
            <p class="lead compact">Действует до {escape(expires)}. До {max_devices} устройств — установите ссылку на каждом.</p>
            <div class="actions">
              <button class="button primary" type="button" onclick="connectClient()">Подключить</button>
              <button class="button" type="button" onclick="copySub()">Скопировать ссылку</button>
              <button class="button" type="button" onclick="toggleQr()">Показать QR</button>
            </div>
            <p class="sub-url" id="subUrl">{escape(subscription_url)}</p>
            <p class="hint" id="connectHint" hidden>Если клиент не открылся, скопируйте ссылку или отсканируйте QR.</p>
            <div class="qr-wrap" id="qrWrap" hidden><img src="/sub/{escape(subscription.token)}/qr" alt="QR код подписки"></div>
            {configs_block}
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
            <p class="instructions-title">Инструкция по установке</p>
            <details open>
              <summary>Windows · v2rayN <span class="tag">основной</span></summary>
              <ol>
                <li>Скачайте v2rayN и распакуйте архив.</li>
                <li>Нажмите «Скопировать ссылку» выше.</li>
                <li>В v2rayN: Subscriptions → Add subscription.</li>
                <li>Вставьте ссылку, сохраните и нажмите Update subscription.</li>
                <li>Выберите сервер и включите системный прокси.</li>
              </ol>
            </details>
            <details>
              <summary>Android · v2rayNG</summary>
              <ol>
                <li>Установите v2rayNG из Google Play.</li>
                <li>Нажмите «Скопировать ссылку» выше.</li>
                <li>«+» → Импорт из буфера обмена.</li>
                <li>Обновите подписку, выберите сервер и подключитесь.</li>
              </ol>
            </details>
            <details>
              <summary>iPhone · Hiddify / Streisand</summary>
              <ol>
                <li>Установите Hiddify или Streisand из App Store.</li>
                <li>Нажмите «Подключить» выше или отсканируйте QR.</li>
                <li>Если не открылось — вставьте скопированную ссылку вручную.</li>
              </ol>
            </details>
            <details>
              <summary>Android · Hiddify</summary>
              <ol>
                <li>Установите Hiddify из Google Play.</li>
                <li>Нажмите «Подключить» или вставьте ссылку подписки.</li>
              </ol>
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
    coin_options: list[dict[str, str]],
) -> str:
    order_ref = subscription.token[:12].upper()
    price_rub = _price(tariff.price_rub)
    coins_js = _coins_js(coin_options)
    coin_blocks = "\n".join(_coin_block(i, opt, subscription.token) for i, opt in enumerate(coin_options))
    return _page(
        "Оплата криптовалютой",
        f"""
        <main class="shell connect">
          <div class="status-card active" style="background:linear-gradient(145deg,rgba(103,247,165,.13),rgba(255,255,255,.08))">
            <p class="eyebrow">Оплата криптовалютой</p>
            <h1>{escape(tariff.title)}</h1>
            <p class="lead compact">Стоимость: <strong>{escape(price_rub)}</strong>&nbsp;&nbsp;·&nbsp;&nbsp;Заказ: <code>{escape(order_ref)}</code></p>
            <p class="lead compact" style="margin-top:6px">Выберите валюту и переведите точную сумму.</p>
            <div class="coin-tabs" id="coinTabs">
              {_coin_tab_buttons(coin_options)}
            </div>
            {coin_blocks}
            <div class="instructions" style="margin-top:18px">
              <details open>
                <summary>Как оплатить</summary>
                <ol>
                  <li>Выберите валюту, которая удобна вам.</li>
                  <li>Откройте ваш кошелёк (Binance, OKX, Bybit, Trust Wallet и др.).</li>
                  <li>Убедитесь, что выбрали правильную <strong>сеть</strong> (TRC20, BSC, TON и т.д.).</li>
                  <li>Переведите <strong>точную сумму</strong> — без округления.</li>
                  <li>В комментарии/мемо укажите номер заказа: <strong>{escape(order_ref)}</strong>.</li>
                  <li>После подтверждения транзакции активируем доступ — обычно в течение 30 минут.</li>
                </ol>
              </details>
            </div>
            <div style="margin-top:20px">
              <a class="button" href="/connect/{escape(subscription.token)}">Проверить статус доступа</a>
            </div>
          </div>
        </main>
        <script>
          {coins_js}
          function selectCoin(idx) {{
            document.querySelectorAll('.coin-panel').forEach((p, i) => p.hidden = i !== idx);
            document.querySelectorAll('.coin-tab').forEach((b, i) => b.classList.toggle('active', i === idx));
          }}
          async function copyAddr(idx) {{
            await navigator.clipboard.writeText(COINS[idx].address);
            const hint = document.getElementById('copyHint' + idx);
            if (hint) hint.hidden = false;
          }}
          function toggleQr(idx) {{
            const qr = document.getElementById('addrQr' + idx);
            if (qr) qr.hidden = !qr.hidden;
          }}
          selectCoin(0);
        </script>
        <style>
          .coin-tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }}
          .coin-tab {{ padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--panel); font: inherit; font-size: .85rem; font-weight: 700; cursor: pointer; color: var(--text); }}
          .coin-tab.active {{ border-color: var(--cyan); color: var(--cyan); background: rgba(54,231,255,.10); }}
          .coin-panel {{ margin-top: 14px; border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: rgba(0,0,0,.22); }}
          .crypto-meta {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
          .crypto-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
          .crypto-net {{ color: var(--muted); font-size: .8rem; }}
          .crypto-amount {{ font-size: 1.9rem; font-weight: 900; margin: 0 0 12px; }}
          .crypto-label {{ margin: 0 0 4px; color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .1em; }}
          .crypto-addr {{ margin: 0 0 12px; font-family: monospace; font-size: .88rem; word-break: break-all; color: var(--cyan); }}
          .hint {{ color: var(--green); margin-top: 8px; }}
          code {{ font-family: monospace; color: var(--cyan); }}
        </style>
        """,
    )


def _configs_block(configs: list[dict[str, str]]) -> str:
    if not configs:
        return ""
    rows = "\n".join(
        f'<li><span class="cfg-name">{escape(c.get("label", ""))}</span>'
        f'<span class="cfg-kind">{escape(c.get("kind", ""))}</span></li>'
        for c in configs
    )
    return f"""
      <div class="configs">
        <p class="configs-title">Доступные варианты ({len(configs)})</p>
        <ul class="configs-list">{rows}</ul>
        <p class="configs-hint">Все варианты добавятся одной ссылкой. Если один не работает — выберите другой в приложении.</p>
      </div>
    """


def _coin_tab_buttons(coin_options: list[dict[str, str]]) -> str:
    parts = []
    for i, opt in enumerate(coin_options):
        dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{escape(opt["color"])};margin-right:5px"></span>'
        parts.append(
            f'<button class="coin-tab" type="button" onclick="selectCoin({i})">'
            f'{dot}{escape(opt["label"])} <span style="opacity:.6;font-weight:400">{escape(opt["network_label"])}</span>'
            f'</button>'
        )
    return "\n".join(parts)


def _coin_block(idx: int, opt: dict[str, str], token: str) -> str:
    return f"""
      <div class="coin-panel" id="coinPanel{idx}" hidden>
        <div class="crypto-meta">
          <span class="crypto-dot" style="background:{escape(opt['color'])}"></span>
          <span style="font-weight:700">{escape(opt['label'])}</span>
          <span class="crypto-net">{escape(opt['network_label'])}</span>
        </div>
        <p class="crypto-amount">{escape(opt['amount'])} {escape(opt['label'])}</p>
        <p class="crypto-label">Адрес кошелька</p>
        <p class="crypto-addr">{escape(opt['address'])}</p>
        <div class="actions">
          <button class="button primary" type="button" onclick="copyAddr({idx})">Скопировать адрес</button>
          <button class="button" type="button" onclick="toggleQr({idx})">QR-код</button>
        </div>
        <div class="qr-wrap" id="addrQr{idx}" hidden>
          <img src="/invoice/{escape(token)}/qr/{escape(opt['id'])}" alt="QR {escape(opt['label'])} {escape(opt['network_label'])}">
        </div>
        <p class="hint" id="copyHint{idx}" hidden>Адрес скопирован.</p>
      </div>
    """


def _coins_js(coin_options: list[dict[str, str]]) -> str:
    import json as _json
    items = [{"address": opt["address"]} for opt in coin_options]
    return f"const COINS = {_json.dumps(items)};"


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
        <p>До {tariff.max_devices} устройств. Ссылка после подтверждения оплаты.</p>
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
    .steps {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .step {{ display: flex; align-items: flex-start; gap: 12px; border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: var(--panel); }}
    .step p {{ margin: 0; color: var(--muted); line-height: 1.45; }}
    .step-num {{ flex-shrink: 0; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: linear-gradient(135deg, var(--cyan), var(--green)); color: #061018; font-weight: 900; }}
    .notes {{ display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); }}
    .notes span {{ border: 1px solid var(--line); border-radius: 999px; padding: 9px 12px; background: rgba(255,255,255,.05); }}
    .configs {{ margin-top: 22px; border-top: 1px solid var(--line); padding-top: 18px; }}
    .configs-title {{ margin: 0 0 12px; font-size: .82rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
    .configs-list {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }}
    .configs-list li {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; background: rgba(0,0,0,.18); }}
    .cfg-name {{ font-weight: 700; }}
    .cfg-kind {{ font-size: .74rem; font-weight: 800; letter-spacing: .04em; color: var(--cyan); background: rgba(54,231,255,.12); border-radius: 999px; padding: 4px 10px; }}
    .configs-hint {{ margin: 12px 0 0; color: var(--muted); font-size: .9rem; line-height: 1.5; }}
    .instructions-title {{ margin: 0; font-size: .82rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
    .tag {{ display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 999px; background: rgba(54,231,255,.16); color: var(--cyan); font-size: .68rem; font-weight: 800; letter-spacing: .04em; vertical-align: middle; }}
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
      .pricing, .compact-pricing, .steps {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: clamp(2.45rem, 15vw, 4rem); }}
      .status-card {{ padding: 18px; }}
      .actions {{ display: grid; grid-template-columns: 1fr; }}
      .button, .primary-link {{ width: 100%; }}
    }}
  </style>
</head>
<body>{body}</body>
</html>"""
