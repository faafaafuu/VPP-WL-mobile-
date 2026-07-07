from __future__ import annotations

import json
from html import escape

from app.domain.models import CommercialSubscription
from app.domain.tariffs import Tariff

# Design tokens from design_handoff_vpn_landing (variant 2a "hacker terminal").
_ACCENTS = (
    ("#00d4ff", "rgba(0,212,255,.35)", "rgba(0,212,255,.05)"),
    ("#ffd60a", "#ffd60a", "rgba(255,214,10,.08)"),
    ("#ff2b4d", "#ff2b4d", "rgba(255,43,77,.08)"),
)


def landing_page(tariffs: tuple[Tariff, ...]) -> str:
    rows = "\n".join(_tariff_row(i, tariff) for i, tariff in enumerate(tariffs))
    steps = """
      <div class="steps">
        <span class="c-cyan">01.</span> оплата криптовалютой<br>
        <span class="c-yellow">02.</span> установка v2rayN / v2rayNG / Hiddify<br>
        <span class="c-red">03.</span> ссылка после подтверждения
      </div>
    """
    return _page(
        "Быстрый VPN-доступ",
        f"""
        <div class="syslog">
          <div class="dim">root@core:~$ nmap -sV target.net</div>
          <div class="c-cyan">[+] host up <span class="dim2">0.014s latency</span></div>
          <div class="c-cyan">[+] 443/tcp <span class="c-green">open</span> encrypted</div>
          <div class="c-red">[!] traffic obfuscation <span class="c-green">ENABLED</span></div>
          <div class="dim">root@core:~$ ./vpn_router --start</div>
        </div>
        <div class="hero">
          <h1>БЫСТРЫЙ_VPN<br>_ДОСТУП<span class="cursor"></span></h1>
          <div class="subhead">// YouTube · Telegram · Instagram · ChatGPT<br>// подключение — 60 сек., без логов</div>
          <a class="cta" href="#pricing">$ выбрать_тариф --run</a>
        </div>
        <div class="tariffs" id="pricing">
          {rows}
        </div>
        {steps}
        <div class="dim" style="padding-bottom:6px">// уже оплатили, но потеряли ссылку? <a href="/recover">восстановить доступ</a></div>
        """,
    )


def connect_page(
    subscription: CommercialSubscription,
    subscription_url: str,
    tariffs: tuple[Tariff, ...],
    invoice_url: str | None = None,
    telegram_link: str | None = None,
) -> str:
    tg_block = ""
    if telegram_link:
        tg_hint = "ссылка всегда будет под рукой + уведомление об оплате" if subscription.tg_chat_id is None else "заказ уже привязан к Telegram"
        tg_block = f"""
            <a class="btn" href="{escape(telegram_link)}" target="_blank" rel="noopener">✈ привязать Telegram</a>
            <p class="hint dim2">// {escape(tg_hint)}</p>
        """
    tariff_map = {t.id: t for t in tariffs}
    current_tariff = tariff_map.get(subscription.tariff_id)
    max_devices = current_tariff.max_devices if current_tariff else 3
    renew_rows = "\n".join(_tariff_row(i, tariff) for i, tariff in enumerate(tariffs))
    if subscription.is_active():
        expires = subscription.expires_at.strftime("%d.%m.%Y") if subscription.expires_at else ""
        status = f"""
          <div class="block block-green">
            <div class="dim">root@core:~$ ./vpn_router --status</div>
            <h1 class="small">Ваш VPN активен<span class="cursor"></span></h1>
            <div class="subhead">// действует до {escape(expires)}<br>// до {max_devices} устройств — установите ссылку на каждом<br>// сохраните адрес этой страницы — потеряли? <a href="/recover">восстановить по TxID</a></div>
            <div class="actions">
              <button class="cta" type="button" onclick="connectClient()">$ подключить --run</button>
              <button class="btn" type="button" onclick="copySub()">Скопировать ссылку</button>
              <button class="btn" type="button" onclick="toggleQr()">Показать QR</button>
            </div>
            <p class="mono-box" id="subUrl">{escape(subscription_url)}</p>
            <p class="hint c-green" id="connectHint" hidden>Если клиент не открылся, скопируйте ссылку или отсканируйте QR.</p>
            <div class="qr-wrap" id="qrWrap" hidden><img src="/sub/{escape(subscription.token)}/qr" alt="QR код подписки"></div>
            {tg_block}
          </div>
        """
    elif subscription.status == "pending":
        pay_href = invoice_url or "/#pricing"
        status = f"""
          <div class="block block-yellow">
            <div class="dim">root@core:~$ ./vpn_router --status</div>
            <h1 class="small c-yellow">Ожидание оплаты<span class="cursor"></span></h1>
            <div class="subhead">// заказ создан, оплата ещё не поступила<br>// после подтверждения сети доступ включится автоматически</div>
            <a class="cta" href="{escape(pay_href)}">$ оплатить --run</a>
            {tg_block}
          </div>
        """
    else:
        status = f"""
          <div class="block block-red">
            <div class="dim">root@core:~$ ./vpn_router --status</div>
            <h1 class="small c-red">Подписка закончилась</h1>
            <div class="subhead">// продлите доступ — ссылка снова заработает автоматически</div>
            <a class="cta" href="/#pricing">$ продлить --run</a>
          </div>
        """
    return _page(
        "Подключение VPN",
        f"""
        {status}
        <div class="guides">
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
        </div>
        <div class="tariffs">
          <div class="dim" style="margin-bottom:4px">root@core:~$ ./vpn_router --renew</div>
          {renew_rows}
        </div>
        <script>
          const subUrl = {subscription_url!r};
          async function copyText(text) {{
            if (navigator.clipboard && window.isSecureContext) {{
              try {{ await navigator.clipboard.writeText(text); return true; }} catch (e) {{}}
            }}
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            let ok = false;
            try {{ ok = document.execCommand('copy'); }} catch (e) {{}}
            document.body.removeChild(ta);
            return ok;
          }}
          async function copySub() {{
            const ok = await copyText(subUrl);
            const hint = document.getElementById('connectHint');
            hint.hidden = false;
            hint.textContent = ok
              ? 'Ссылка скопирована. Вставьте её в ваш VPN-клиент.'
              : 'Не удалось скопировать — выделите ссылку ниже и скопируйте вручную.';
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
    telegram_link: str | None = None,
) -> str:
    tg_block = ""
    if telegram_link:
        tg_block = f"""
        <div class="actions">
          <a class="btn" href="{escape(telegram_link)}" target="_blank" rel="noopener">✈ привязать Telegram</a>
        </div>
        <p class="hint dim2">// бот пришлёт ссылку сразу после подтверждения оплаты — и вы её никогда не потеряете</p>
        """
    token = subscription.token
    order_ref = token[:12].upper()
    price_rub = _price(tariff.price_rub)
    coins_js = json.dumps(
        [
            {
                "id": opt["id"],
                "label": opt["label"],
                "network_label": opt["network_label"],
                "amount": opt["amount"],
                "address": opt["address"],
            }
            for opt in coin_options
        ],
        ensure_ascii=False,
    )
    coin_blocks = "\n".join(_coin_block(i, opt, token) for i, opt in enumerate(coin_options))
    return _page(
        "Оплата криптовалютой",
        f"""
        <div class="block block-green">
          <div class="dim">root@core:~$ ./vpn_router --pay</div>
          <h1 class="small">{escape(tariff.title)}<span class="cursor"></span></h1>
          <div class="subhead">// стоимость: <span class="c-white">{escape(price_rub)}</span> · заказ: <code>{escape(order_ref)}</code><br>// выберите валюту и переведите точную сумму</div>
          <div class="coin-tabs" id="coinTabs">
            {_coin_tab_buttons(coin_options)}
          </div>
          {coin_blocks}
          <p class="hint c-yellow" id="watchState">ожидание выбора валюты…</p>
        </div>
        <div class="guides">
          <details open>
            <summary>Как оплатить</summary>
            <ol>
              <li>Выберите валюту, которая удобна вам.</li>
              <li>Откройте ваш кошелёк (Binance, OKX, Bybit, Trust Wallet и др.).</li>
              <li>Убедитесь, что выбрали правильную <strong>сеть</strong> (TRC20, BSC и т.д.).</li>
              <li>Переведите <strong>точную сумму</strong> — без округления, до последнего знака.</li>
              <li>После подтверждения в сети доступ включится автоматически — страница обновится сама.</li>
            </ol>
          </details>
        </div>
        <div class="actions">
          <a class="btn" href="/connect/{escape(token)}">Проверить статус доступа</a>
        </div>
        {tg_block}
        <p class="dim" style="margin-top:14px">// сохраните ссылку на эту страницу — по ней вы всегда вернётесь к заказу.<br>// потеряли? <a href="/recover">восстановить доступ по TxID</a></p>
        <script>
          const COINS = {coins_js};
          const TOKEN = {token!r};
          let selectedIdx = null;
          let pollTimer = null;

          async function selectCoin(idx) {{
            selectedIdx = idx;
            document.querySelectorAll('.coin-panel').forEach((p, i) => p.hidden = i !== idx);
            document.querySelectorAll('.coin-tab').forEach((b, i) => b.classList.toggle('active', i === idx));
            const state = document.getElementById('watchState');
            try {{
              const resp = await fetch('/invoice/' + TOKEN + '/select', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{coin_id: COINS[idx].id}}),
              }});
              const data = await resp.json();
              if (data.status === 'active') {{ window.location = data.connect_url; return; }}
              if (data.amount) {{
                COINS[idx].amount = data.amount;
                COINS[idx].address = data.address;
                document.getElementById('amount' + idx).textContent = data.amount + ' ' + COINS[idx].label;
                document.getElementById('addr' + idx).textContent = data.address;
                state.textContent = 'переведите ровно ' + data.amount + ' ' + COINS[idx].label +
                  ' — доступ включится автоматически после подтверждения сети';
                startPolling();
              }}
            }} catch (e) {{
              state.textContent = 'не удалось получить сумму — обновите страницу';
            }}
          }}
          function startPolling() {{
            if (pollTimer) return;
            pollTimer = setInterval(async () => {{
              try {{
                const resp = await fetch('/invoice/' + TOKEN + '/status');
                const data = await resp.json();
                if (data.status === 'active') {{
                  clearInterval(pollTimer);
                  window.location = data.connect_url;
                }}
              }} catch (e) {{}}
            }}, 5000);
          }}
          async function copyText(text) {{
            if (navigator.clipboard && window.isSecureContext) {{
              try {{ await navigator.clipboard.writeText(text); return true; }} catch (e) {{}}
            }}
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            let ok = false;
            try {{ ok = document.execCommand('copy'); }} catch (e) {{}}
            document.body.removeChild(ta);
            return ok;
          }}
          async function copyAddr(idx) {{
            await copyText(COINS[idx].address);
            const hint = document.getElementById('copyHint' + idx);
            if (hint) hint.hidden = false;
          }}
          async function copyAmount(idx) {{
            await copyText(COINS[idx].amount);
          }}
          function toggleQr(idx) {{
            const qr = document.getElementById('addrQr' + idx);
            if (qr) qr.hidden = !qr.hidden;
          }}
          selectCoin(0);
          startPolling();
        </script>
        """,
    )


def recover_page(error: str | None = None, telegram_bot: str | None = None) -> str:
    error_html = f'<p class="hint c-red">{escape(error)}</p>' if error else ""
    tg_block = ""
    if telegram_bot:
        tg_block = f"""
        <div class="block block-green">
          <div class="dim">root@core:~$ ./vpn_router --recover --via telegram</div>
          <div class="subhead">// привязывали заказ к Telegram? бот помнит ваши ссылки</div>
          <a class="btn" href="https://t.me/{escape(telegram_bot)}" target="_blank" rel="noopener">✈ открыть бота @{escape(telegram_bot)}</a>
        </div>
        """
    return _page(
        "Восстановление доступа",
        f"""
        <div class="block block-green">
          <div class="dim">root@core:~$ ./vpn_router --recover</div>
          <h1 class="small">Восстановление доступа<span class="cursor"></span></h1>
          <div class="subhead">// оплатили, но потеряли ссылку?<br>// введите хэш транзакции (TxID) или адрес кошелька, с которого платили</div>
          <form method="post" action="/recover">
            <input class="field" type="text" name="query" placeholder="TxID или адрес отправителя" required minlength="8" autocomplete="off" spellcheck="false">
            <button class="cta" type="submit">$ найти_заказ --run</button>
          </form>
          {error_html}
          <div class="subhead">// TxID (hash) можно найти в истории вашего кошелька или биржи<br>// не находится? напишите нам и приложите TxID</div>
        </div>
        {tg_block}
        """,
    )


def admin_orders_page(orders: list[dict[str, str]]) -> str:
    status_colors = {"active": "c-green", "pending": "c-yellow"}
    rows = []
    for order in orders:
        cls = status_colors.get(order["status"], "c-red")
        rows.append(
            "<tr>"
            f'<td><a href="{escape(order["connect_url"])}"><code>{escape(order["order_ref"])}</code></a></td>'
            f'<td>{escape(order["tariff_id"])}</td>'
            f'<td class="{cls}">{escape(order["status"])}</td>'
            f'<td>{escape(order["created_at"])}</td>'
            f'<td>{escape(order["expires_at"])}</td>'
            f'<td>{escape(order["payment"])}</td>'
            f'<td class="tx">{escape(order["paid_tx"])}</td>'
            f'<td class="tx">{escape(order["payer"])}</td>'
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="8" class="dim">заказов пока нет</td></tr>'
    return _page(
        "Заказы",
        f"""
        <div class="block block-green">
          <div class="dim">root@core:~$ ./vpn_router --orders</div>
          <h1 class="small">Заказы<span class="cursor"></span></h1>
          <div class="subhead">// все заказы, новые сверху · pending = ждёт оплату · active = оплачен</div>
        </div>
        <div class="table-wrap">
          <table class="orders">
            <tr><th>заказ</th><th>тариф</th><th>статус</th><th>создан</th><th>до</th><th>оплата</th><th>tx</th><th>плательщик</th></tr>
            {body}
          </table>
        </div>
        """,
    )


def not_found_page() -> str:
    return _page(
        "Ссылка не найдена",
        """
        <div class="block block-red">
          <div class="dim">root@core:~$ ./vpn_router --connect</div>
          <h1 class="small c-red">404: ссылка не найдена</h1>
          <div class="subhead">// проверьте адрес или оформите новый доступ</div>
          <a class="cta" href="/#pricing">$ выбрать_тариф --run</a>
        </div>
        """,
    )


def _tariff_row(idx: int, tariff: Tariff) -> str:
    accent, border, background = _ACCENTS[idx % len(_ACCENTS)]
    months = max(tariff.duration_days // 30, 1)
    badge = f' <span class="badge">// {escape(tariff.badge)}</span>' if tariff.badge else ""
    return f"""
      <form method="post" action="/checkout" class="tariff-form">
        <input type="hidden" name="tariff_id" value="{escape(tariff.id)}">
        <button class="tariff" type="submit" style="border-color:{border};background:{background}">
          <span style="color:{accent}">[{months:02d}] {escape(tariff.title)}{badge}</span>
          <span class="price">{escape(_price(tariff.price_rub))}</span>
        </button>
      </form>
    """


def _coin_tab_buttons(coin_options: list[dict[str, str]]) -> str:
    parts = []
    for i, opt in enumerate(coin_options):
        parts.append(
            f'<button class="coin-tab" type="button" onclick="selectCoin({i})">'
            f'<span class="coin-dot" style="background:{escape(opt["color"])}"></span>'
            f'{escape(opt["label"])} <span class="coin-net">{escape(opt["network_label"])}</span>'
            f'</button>'
        )
    return "\n".join(parts)


def _coin_block(idx: int, opt: dict[str, str], token: str) -> str:
    return f"""
      <div class="coin-panel" id="coinPanel{idx}" hidden>
        <div class="crypto-meta">
          <span class="coin-dot" style="background:{escape(opt['color'])}"></span>
          <span class="c-white">{escape(opt['label'])}</span>
          <span class="coin-net">{escape(opt['network_label'])}</span>
        </div>
        <p class="crypto-amount" id="amount{idx}" onclick="copyAmount({idx})">{escape(opt['amount'])} {escape(opt['label'])}</p>
        <p class="crypto-label">адрес кошелька</p>
        <p class="crypto-addr" id="addr{idx}">{escape(opt['address'])}</p>
        <div class="actions">
          <button class="cta" type="button" onclick="copyAddr({idx})">$ скопировать_адрес</button>
          <button class="btn" type="button" onclick="toggleQr({idx})">QR-код</button>
        </div>
        <div class="qr-wrap" id="addrQr{idx}" hidden>
          <img src="/invoice/{escape(token)}/qr/{escape(opt['id'])}" alt="QR {escape(opt['label'])} {escape(opt['network_label'])}">
        </div>
        <p class="hint c-green" id="copyHint{idx}" hidden>Адрес скопирован.</p>
      </div>
    """


def _price(raw: str) -> str:
    if raw.endswith(".00"):
        raw = raw[:-3]
    return f"{raw}₽"


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050705;
      --green: #00ff41;
      --green-dim: rgba(0,255,65,.45);
      --green-dim2: rgba(0,255,65,.55);
      --green-mute: rgba(0,255,65,.35);
      --green-line: rgba(0,255,65,.3);
      --cyan: #00d4ff;
      --yellow: #ffd60a;
      --red: #ff2b4d;
      --white: #fff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: 'Share Tech Mono', monospace;
      color: var(--green);
      background: var(--bg);
      background-image:
        linear-gradient(rgba(0,255,65,.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,65,.03) 1px, transparent 1px);
      background-size: 22px 22px;
      display: flex;
      justify-content: center;
      padding: 24px 12px 48px;
    }}
    a {{ color: inherit; }}
    .term {{ width: min(560px, 100%); border: 1px solid var(--green-line); background: rgba(5,7,5,.75); }}
    .term-bar {{
      padding: 14px 22px; border-bottom: 1px solid var(--green-line);
      display: flex; justify-content: space-between; align-items: center;
    }}
    .term-dots {{ display: flex; gap: 6px; }}
    .term-dots span {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
    .term-title {{ font-size: 11px; color: rgba(0,255,65,.5); }}
    .term-body {{ padding: 20px 22px 24px; }}
    .syslog {{ font-size: 12px; line-height: 1.7; margin-bottom: 18px; }}
    .dim {{ color: var(--green-dim); font-size: 12px; line-height: 1.7; }}
    .dim2 {{ color: rgba(0,255,65,.5); }}
    .c-cyan {{ color: var(--cyan); }}
    .c-yellow {{ color: var(--yellow); }}
    .c-red {{ color: var(--red); }}
    .c-green {{ color: var(--green); }}
    .c-white {{ color: var(--white); }}
    h1 {{
      margin: 0; font-size: 27px; line-height: 1.3; font-weight: 800;
      color: var(--green); text-shadow: 0 0 10px rgba(0,255,65,.6); letter-spacing: 0;
    }}
    h1.small {{ font-size: 22px; }}
    .cursor {{
      display: inline-block; width: 12px; height: 22px; background: var(--green);
      margin-left: 4px; vertical-align: middle; animation: blink 1s step-end infinite;
    }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    .subhead {{ margin-top: 14px; font-size: 12px; line-height: 1.8; color: var(--green-dim2); overflow-wrap: anywhere; }}
    .cta {{
      display: inline-block; margin-top: 20px; padding: 12px 22px; min-height: 44px;
      background: var(--green); color: #020402; font: inherit; font-size: 13px; font-weight: 800;
      text-decoration: none; border: 0; cursor: pointer;
      box-shadow: 0 0 18px rgba(0,255,65,.45); transition: filter .15s, box-shadow .15s;
    }}
    .cta:hover {{ filter: brightness(1.25); box-shadow: 0 0 26px rgba(0,255,65,.45); }}
    .btn {{
      display: inline-block; margin-top: 20px; padding: 12px 22px; min-height: 44px;
      background: transparent; color: var(--green); font: inherit; font-size: 13px; font-weight: 700;
      text-decoration: none; border: 1px solid var(--green-line); cursor: pointer; transition: filter .15s;
    }}
    .btn:hover {{ filter: brightness(1.25); background: rgba(0,255,65,.06); }}
    .hero {{ padding: 18px 0 24px; }}
    .tariffs {{ display: flex; flex-direction: column; gap: 8px; padding: 0 0 20px; font-size: 12px; }}
    .tariff-form {{ margin: 0; }}
    .tariff {{
      width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 10px;
      padding: 12px 14px; min-height: 44px; border: 1px solid; font: inherit; font-size: 12px;
      cursor: pointer; text-align: left; transition: filter .15s;
    }}
    .tariff:hover {{ filter: brightness(1.3); }}
    .badge {{ opacity: .7; }}
    .price {{ color: var(--white); font-weight: 700; white-space: nowrap; }}
    .steps {{ padding: 0 0 26px; font-size: 12px; line-height: 2; color: var(--green-dim2); }}
    .status-bar {{
      padding: 10px 22px 18px; border-top: 1px dashed rgba(0,255,65,.25);
      font-size: 11px; color: var(--green-mute);
    }}
    .block {{ border: 1px solid var(--green-line); padding: 16px; margin-bottom: 18px; }}
    .block-green {{ background: rgba(0,255,65,.04); }}
    .block-red {{ border-color: rgba(255,43,77,.5); background: rgba(255,43,77,.05); }}
    .block-yellow {{ border-color: rgba(255,214,10,.5); background: rgba(255,214,10,.05); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .actions .cta, .actions .btn {{ margin-top: 14px; }}
    .mono-box {{
      overflow-wrap: anywhere; color: var(--green-dim2); border: 1px solid var(--green-line);
      padding: 12px; background: rgba(0,0,0,.35); font-size: 12px; margin: 16px 0 0;
    }}
    .hint {{ font-size: 12px; margin: 10px 0 0; }}
    .qr-wrap {{ width: min(280px, 100%); margin-top: 14px; padding: 12px; background: #fff; }}
    .qr-wrap img {{ display: block; width: 100%; height: auto; }}
    .guides {{ display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px; }}
    .guides details {{ border: 1px solid var(--green-line); background: rgba(0,255,65,.03); }}
    .guides summary {{ padding: 12px 14px; cursor: pointer; font-size: 12px; font-weight: 700; }}
    .guides ol {{ margin: 0; padding: 0 18px 14px 32px; font-size: 12px; line-height: 1.9; color: var(--green-dim2); }}
    code {{ color: var(--cyan); }}
    .coin-tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .coin-tab {{
      padding: 10px 14px; min-height: 40px; border: 1px solid var(--green-line); background: transparent;
      font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; color: var(--green);
    }}
    .coin-tab.active {{ border-color: var(--cyan); color: var(--cyan); background: rgba(0,212,255,.08); }}
    .coin-panel {{ margin-top: 14px; border: 1px solid var(--green-line); padding: 14px; background: rgba(0,0,0,.3); }}
    .coin-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}
    .coin-net {{ color: var(--green-mute); font-size: 11px; }}
    .crypto-meta {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 12px; }}
    .crypto-amount {{ font-size: 24px; font-weight: 800; margin: 0 0 12px; color: var(--white); cursor: pointer; }}
    .crypto-label {{ margin: 0 0 4px; color: var(--green-mute); font-size: 11px; text-transform: uppercase; letter-spacing: .1em; }}
    .crypto-addr {{ margin: 0; font-size: 12px; word-break: break-all; color: var(--cyan); }}
    .field {{
      width: 100%; margin-top: 20px; padding: 12px 14px; min-height: 44px;
      background: rgba(0,0,0,.35); border: 1px solid var(--green-line); color: var(--green);
      font: inherit; font-size: 13px;
    }}
    .field:focus {{ outline: none; border-color: var(--green); }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--green-line); }}
    .orders {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    .orders th, .orders td {{ border: 1px solid var(--green-line); padding: 6px 8px; text-align: left; white-space: nowrap; }}
    .orders th {{ color: var(--green-mute); font-weight: 700; }}
    .orders .tx {{ max-width: 140px; overflow: hidden; text-overflow: ellipsis; }}
    @media (max-width: 480px) {{
      body {{ padding: 0 0 32px; }}
      .term {{ border-left: 0; border-right: 0; }}
      .actions {{ flex-direction: column; }}
      .actions .cta, .actions .btn, .cta, .btn {{ width: 100%; text-align: center; }}
    }}
  </style>
</head>
<body>
  <div class="term">
    <div class="term-bar">
      <div class="term-dots"><span style="background:#ff2b4d"></span><span style="background:#ffd60a"></span><span style="background:#00ff41"></span></div>
      <span class="term-title">vpn-router — bash — 80×24</span>
    </div>
    <div class="term-body">{body}</div>
    <div class="status-bar">STATUS: <span class="c-green">CONNECTED</span> · UPTIME 99.98% · ENCRYPTION AES-256</div>
  </div>
</body>
</html>"""
