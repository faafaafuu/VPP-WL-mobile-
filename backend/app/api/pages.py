from __future__ import annotations

import json
from decimal import Decimal
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
    base_monthly = _base_monthly_price(tariffs)
    rows = "\n".join(_tariff_row(i, tariff, base_monthly) for i, tariff in enumerate(tariffs))
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
        <div class="footer-links">Оплачивая тариф, вы принимаете <a href="/terms">публичную оферту</a> и <a href="/privacy">политику конфиденциальности</a>.</div>
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
    traffic_gb = current_tariff.traffic_gb if current_tariff else 0
    traffic_note = f"{traffic_gb} ГБ трафика" if traffic_gb else "трафик без ограничений"
    renew_base_monthly = _base_monthly_price(tariffs)
    renew_rows = "\n".join(_tariff_row(i, tariff, renew_base_monthly) for i, tariff in enumerate(tariffs))
    if subscription.is_active():
        expires = subscription.expires_at.strftime("%d.%m.%Y") if subscription.expires_at else ""
        status = f"""
          <div class="block block-green">
            <div class="dim">root@core:~$ ./vpn_router --status</div>
            <h1 class="small">Ваш VPN активен<span class="cursor"></span></h1>
            <div class="subhead">// действует до {escape(expires)}<br>// до {max_devices} устройств, {escape(traffic_note)}<br>// сохраните адрес этой страницы — потеряли? <a href="/recover">восстановить по email</a></div>
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
            <summary>iPhone / iPad</summary>
            <ol><li>Установите <a href="https://apps.apple.com/us/search?term=Hiddify" target="_blank" rel="noopener">Hiddify</a> из App Store (стор сам ставит последнюю версию).</li><li>Нажмите “Подключить”.</li><li>Если не открылось, отсканируйте QR или вставьте ссылку.</li></ol>
          </details>
          <details>
            <summary>Android</summary>
            <ol><li>Установите <a href="https://github.com/hiddify/hiddify-app/releases/latest/download/Hiddify-Android-universal.apk">Hiddify (.apk, сразу скачается последняя версия)</a>.</li><li>Нажмите “Подключить” или вставьте ссылку подписки.</li></ol>
          </details>
          <details>
            <summary>Windows</summary>
            <ol><li>Установите <a href="https://github.com/hiddify/hiddify-app/releases/latest/download/Hiddify-Windows-Setup-x64.exe">Hiddify (.exe, сразу скачается последняя версия)</a>.</li><li>Нажмите “Подключить” или вставьте ссылку подписки.</li></ol>
          </details>
          <details>
            <summary>macOS</summary>
            <ol><li>Установите <a href="https://github.com/hiddify/hiddify-app/releases/latest/download/Hiddify-MacOS.dmg">Hiddify (.dmg, сразу скачается последняя версия)</a>.</li><li>Нажмите “Подключить” или вставьте ссылку подписки.</li></ol>
          </details>
          <details>
            <summary>Linux</summary>
            <ol><li>Установите <a href="https://github.com/hiddify/hiddify-app/releases/latest/download/Hiddify-Linux-x64-AppImage.AppImage">Hiddify (.AppImage, сразу скачается последняя версия)</a>, дайте файлу права на запуск.</li><li>Нажмите “Подключить” или вставьте ссылку подписки.</li></ol>
          </details>
          <p class="dim" style="margin-top:2px">// один и тот же клиент на всех платформах — Hiddify. Уже пользуетесь v2rayNG / v2rayN / Streisand / Shadowrocket? Они тоже подходят — просто вставьте туда ссылку подписки.</p>
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
    saved_email = subscription.customer_email or ""
    contact_block = f"""
        <div class="block">
          <div class="dim">root@core:~$ ./vpn_router --bind email</div>
          <div class="subhead">// нет доступа к Telegram? оставьте email —<br>// по нему вы всегда восстановите ссылку на <a href="/recover">/recover</a></div>
          <input class="field" type="email" id="contactEmail" placeholder="you@example.com" value="{escape(saved_email)}" autocomplete="email">
          <div class="actions">
            <button class="btn" type="button" onclick="saveEmail()">сохранить email</button>
          </div>
          <p class="hint" id="emailHint" hidden></p>
        </div>
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
          <div class="footer-links" style="margin:0 0 10px"><a href="/#pricing">&larr; сменить тариф</a></div>
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
        {contact_block}
        <p class="dim" style="margin-top:14px">// сохраните ссылку на эту страницу — по ней вы всегда вернётесь к заказу.<br>// потеряли? <a href="/recover">восстановить доступ по email</a></p>
        <script>
          const COINS = {coins_js};
          const TOKEN = {token!r};
          let selectedIdx = null;
          let pollTimer = null;

          async function selectCoin(idx) {{
            selectedIdx = idx;
            document.querySelectorAll('.coin-panel').forEach((p, i) => p.hidden = i !== idx);
            document.querySelectorAll('.coin-tab').forEach(b => b.classList.toggle('active', parseInt(b.dataset.idx) === idx));
            document.querySelectorAll('.coin-select').forEach(s => {{
              if ([...s.options].some(o => parseInt(o.value) === idx)) s.value = idx;
            }});
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
          async function saveEmail() {{
            const input = document.getElementById('contactEmail');
            const hint = document.getElementById('emailHint');
            hint.hidden = false;
            try {{
              const resp = await fetch('/invoice/' + TOKEN + '/contact', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{email: input.value}}),
              }});
              if (resp.ok) {{
                hint.className = 'hint c-green';
                hint.textContent = 'Email сохранён — по нему можно восстановить ссылку.';
              }} else {{
                hint.className = 'hint c-red';
                hint.textContent = 'Проверьте адрес — похоже, в нём опечатка.';
              }}
            }} catch (e) {{
              hint.className = 'hint c-red';
              hint.textContent = 'Не удалось сохранить — попробуйте ещё раз.';
            }}
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
          <div class="subhead">// оплатили, но потеряли ссылку?<br>// введите email, указанный при оплате<br>// (TxID и адрес кошелька для этого не подходят — они видны в блокчейне всем, не только вам)</div>
          <form method="post" action="/recover">
            <input class="field" type="email" name="query" placeholder="email, указанный при оплате" required minlength="8" autocomplete="email" spellcheck="false">
            <button class="cta" type="submit">$ найти_заказ --run</button>
          </form>
          {error_html}
          <div class="subhead">// не указывали email при оплате? напишите нам и приложите TxID — мы сверим вручную</div>
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
            f'<td>{escape(order["email"])}</td>'
            f'<td>{escape(order["tg"])}</td>'
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="10" class="dim">заказов пока нет</td></tr>'
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
            <tr><th>заказ</th><th>тариф</th><th>статус</th><th>создан</th><th>до</th><th>оплата</th><th>tx</th><th>плательщик</th><th>email</th><th>tg</th></tr>
            {body}
          </table>
        </div>
        """,
    )


def privacy_page(support_email: str | None = None) -> str:
    contact = escape(support_email) if support_email else "[email оператора — заполнить]"
    return _page(
        "Политика конфиденциальности",
        f"""
        <div class="block block-green">
          <div class="dim">root@core:~$ cat privacy_policy.txt</div>
          <h1 class="small">Политика конфиденциальности<span class="cursor"></span></h1>
          <div class="subhead">// в соответствии со ст. 18.1 152-ФЗ «О персональных данных»</div>
        </div>
        <div class="legal-text">
          <p><strong>Оператор:</strong> лицо, администрирующее данный сервис (на момент публикации — без регистрации юридического лица/ИП). Контакт по вопросам персональных данных: {contact}.</p>

          <h2>1. Какие данные обрабатываются</h2>
          <p>Мы собираем только то, что необходимо для оказания услуги и приёма оплаты:</p>
          <ul>
            <li>идентификатор устройства/подписки (генерируется автоматически, не содержит имени владельца);</li>
            <li>email — только если вы сами указали его для получения ссылки или восстановления доступа;</li>
            <li>Telegram chat ID — только если вы сами привязали заказ к боту;</li>
            <li>реквизиты платежа: номер платежа ЮKassa, либо для криптоплатежей — публичный хеш транзакции и адрес отправителя (эти данные и так открыты в блокчейне, мы их не публикуем нигде дополнительно);</li>
            <li>служебные события администрирования (без содержимого VPN-конфигов и без ключей доступа).</li>
          </ul>
          <p><strong>Мы не ведём журналы посещённых сайтов и не сохраняем IP-адрес постоянно</strong> — он используется только в оперативной памяти для защиты от перебора запросов и никуда не записывается.</p>

          <h2>2. Цели обработки</h2>
          <p>Заключение и исполнение договора оказания услуг (публичная оферта — см. <a href="/terms">/terms</a>), приём оплаты, восстановление доступа по вашему запросу, техническая поддержка.</p>

          <h2>3. Правовое основание</h2>
          <p>Согласие субъекта персональных данных (ст. 6 152-ФЗ), выражаемое оплатой услуги и/или добровольным указанием email/Telegram.</p>

          <h2>4. Передача третьим лицам</h2>
          <p>Данные платежа передаются платёжному агрегатору (ЮKassa) для обработки оплаты картой; для криптоплатежей данные о транзакции по своей природе публичны в соответствующем блокчейне. При использовании Telegram-бота часть данных обрабатывается Telegram согласно его политике. Мы не продаём и не передаём данные в иных целях.</p>

          <h2>5. Сроки хранения</h2>
          <p>Данные о подписке хранятся, пока это нужно для исполнения договора и учёта платежей; служебные журналы администрирования автоматически удаляются по истечении срока хранения, настроенного оператором (по умолчанию 30 дней).</p>

          <h2>6. Ваши права</h2>
          <p>Вы можете в любой момент запросить копию своих данных или их удаление через раздел приложения «Аккаунт» (экспорт/удаление данных выполняются автоматически по запросу) либо написав на {contact}.</p>

          <h2>7. Важное уточнение</h2>
          <p>Сервис предоставляет технологию защищённого сетевого соединения. Использование сервиса для доступа к информации, распространение которой запрещено законодательством РФ, не допускается и не является целью сервиса.</p>

          <p class="dim" style="margin-top:24px">// черновик, требует проверки юристом перед публикацией</p>
        </div>
        """,
    )


def terms_page(support_email: str | None = None) -> str:
    contact = escape(support_email) if support_email else "[email оператора — заполнить]"
    return _page(
        "Публичная оферта",
        f"""
        <div class="block block-green">
          <div class="dim">root@core:~$ cat public_offer.txt</div>
          <h1 class="small">Публичная оферта<span class="cursor"></span></h1>
          <div class="subhead">// договор оказания услуг, ст. 437 ГК РФ</div>
        </div>
        <div class="legal-text">
          <p><strong>Исполнитель:</strong> лицо, администрирующее данный сервис (на момент публикации — без регистрации юридического лица/ИП). Контакт: {contact}.</p>

          <h2>1. Предмет договора</h2>
          <p>Исполнитель предоставляет Заказчику доступ к технологии защищённого сетевого соединения (VPN) на условиях выбранного тарифа. Оплата (переход по кнопке тарифа и/или подтверждение платежа) означает акцепт настоящей оферты в полном объёме.</p>

          <h2>2. Стоимость и оплата</h2>
          <p>Актуальная стоимость тарифов указана на главной странице сервиса. Способ оплаты — тот, что предложен на странице оплаты (криптовалюта на указанный адрес; оплата картой через ЮKassa становится доступна после регистрации ИП/юрлица и подключения приёма платежей). Услуга — цифровая, доступ предоставляется автоматически после подтверждения оплаты.</p>

          <h2>3. Срок действия и продление</h2>
          <p>Доступ предоставляется на срок, соответствующий оплаченному тарифу. Автоматическое списание за продление не производится — для продолжения пользования услугой требуется повторная оплата.</p>

          <h2>4. Возврат средств</h2>
          <p>[Условия возврата — заполнить и согласовать с юристом; учтите, что для цифровых услуг, доступ к которым уже предоставлен, право на отказ по ст. 26.1 закона «О защите прав потребителей» ограничено].</p>

          <h2>5. Обязанности Заказчика</h2>
          <p>Заказчик обязуется не использовать услугу для действий, запрещённых законодательством РФ, включая доступ к информации, распространение которой ограничено в соответствии с реестром Роскомнадзора, для рассылки спама, проведения атак на инфраструктуру третьих лиц или иных противоправных действий. Исполнитель вправе прекратить оказание услуги при выявлении такого использования.</p>

          <h2>6. Ограничение ответственности</h2>
          <p>Услуга предоставляется «как есть». Исполнитель не гарантирует доступность конкретных внешних ресурсов и не несёт ответственности за действия Заказчика с использованием услуги.</p>

          <h2>7. Реквизиты и споры</h2>
          <p>Споры разрешаются в соответствии с законодательством РФ по месту нахождения Исполнителя. Реквизиты Исполнителя — см. п. «Исполнитель» выше.</p>

          <p class="dim" style="margin-top:24px">// черновик, требует проверки юристом перед публикацией — заполните раздел про возврат средств</p>
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


def _base_monthly_price(tariffs: tuple[Tariff, ...]) -> Decimal | None:
    """Per-month price of the shortest tariff — the reference "no discount"
    rate every other tariff's savings badge is computed against."""
    if not tariffs:
        return None
    shortest = min(tariffs, key=lambda t: t.duration_days)
    months = max(shortest.duration_days // 30, 1)
    return Decimal(shortest.price_rub) / months


def _tariff_row(idx: int, tariff: Tariff, base_monthly: Decimal | None = None) -> str:
    accent, border, background = _ACCENTS[idx % len(_ACCENTS)]
    months = max(tariff.duration_days // 30, 1)
    badge = f' <span class="badge">// {escape(tariff.badge)}</span>' if tariff.badge else ""
    price = Decimal(tariff.price_rub)
    per_month = f"{escape(_price(f'{(price / months):.2f}'))}/мес"
    traffic_note = f"{tariff.traffic_gb} ГБ" if tariff.traffic_gb else "безлимит"
    per_month += f" · {tariff.max_devices} устр. · {escape(traffic_note)}"

    price_block = f'<span class="price">{escape(_price(tariff.price_rub))}</span>'
    if base_monthly is not None and months > 1:
        full_price = base_monthly * months
        if full_price > price:
            discount_pct = round((1 - price / full_price) * 100)
            price_block = (
                f'<span class="price-old">{escape(_price(f"{full_price:.2f}"))}</span>'
                f'<span class="price">{escape(_price(tariff.price_rub))}</span>'
                f'<span class="discount-tag">-{discount_pct}%</span>'
            )

    return f"""
      <form method="post" action="/checkout" class="tariff-form">
        <input type="hidden" name="tariff_id" value="{escape(tariff.id)}">
        <button class="tariff" type="submit" style="border-color:{border};background:{background}">
          <span class="tariff-info">
            <span style="color:{accent}">[{months:02d}] {escape(tariff.title)}{badge}</span>
            <span class="tariff-permo">{per_month}</span>
          </span>
          <span class="tariff-price-block">{price_block}</span>
        </button>
      </form>
    """


def _coin_tab_buttons(coin_options: list[dict[str, str]]) -> str:
    """Groups consecutive options that share a label (e.g. every USDT network)
    under one asset header with network-only chips underneath, instead of
    repeating "USDT" on every chip — coin_options is already asset-grouped by
    ALL_COINS's declaration order. An asset with multiple networks (USDT/USDC)
    gets one row with a network dropdown (defaulting to ERC20, changing it
    selects that coin right away); an asset with only one network (TON/SOL/
    ETH/BTC) is a plain chip. All the single-network chips share one row at
    the end so the picker reads as a couple of neat rows, not one column."""
    groups: list[tuple[str, list[tuple[int, dict[str, str]]]]] = []
    for i, opt in enumerate(coin_options):
        if groups and groups[-1][0] == opt["label"]:
            groups[-1][1].append((i, opt))
        else:
            groups.append((opt["label"], [(i, opt)]))

    parts = []
    singles: list[tuple[int, dict[str, str]]] = []
    for label, entries in groups:
        if len(entries) == 1:
            singles.append(entries[0])
            continue
        default_i = next((i for i, opt in entries if opt["network_label"].startswith("ERC20")), entries[0][0])
        options = "\n".join(
            f'<option value="{i}"{" selected" if i == default_i else ""}>{escape(opt["network_label"])}</option>'
            for i, opt in entries
        )
        parts.append(
            f'<div class="coin-group">'
            f'<div class="coin-group-label"><span class="coin-dot" style="background:{escape(entries[0][1]["color"])}"></span>{escape(label)}</div>'
            f'<select class="coin-select" onchange="selectCoin(parseInt(this.value))">{options}</select>'
            f'</div>'
        )
    if singles:
        chips = "\n".join(
            f'<button class="coin-tab" type="button" data-idx="{i}" onclick="selectCoin({i})">'
            f'<span class="coin-dot" style="background:{escape(opt["color"])}"></span>'
            f'{escape(opt["label"])}'
            f'</button>'
            for i, opt in singles
        )
        parts.append(f'<div class="coin-group-chips">{chips}</div>')
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
    .tariff-info {{ display: flex; flex-direction: column; gap: 3px; }}
    .tariff-permo {{ font-size: 11px; color: var(--green-dim2); }}
    .tariff-price-block {{ display: flex; align-items: baseline; gap: 6px; white-space: nowrap; }}
    .price {{ color: var(--white); font-weight: 700; white-space: nowrap; }}
    .price-old {{ color: var(--green-mute); text-decoration: line-through; font-size: 11px; font-weight: 400; }}
    .discount-tag {{
      background: var(--red); color: var(--white); font-weight: 800; font-size: 10px;
      padding: 2px 6px; border-radius: 3px; letter-spacing: .02em;
    }}
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
    .coin-tabs {{ display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }}
    .coin-group {{ display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }}
    .coin-group-label {{
      display: flex; align-items: center; gap: 6px; min-width: 52px;
      font-size: 12px; font-weight: 700; color: var(--white);
    }}
    .coin-group-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .coin-select {{
      padding: 10px 12px; min-height: 40px; border: 1px solid var(--green-line); background: rgba(0,0,0,.35);
      font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; color: var(--green);
    }}
    .coin-select:focus {{ outline: none; border-color: var(--cyan); }}
    .coin-tab {{
      padding: 10px 14px; min-height: 40px; border: 1px solid var(--green-line); background: transparent;
      font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; color: var(--green);
    }}
    .coin-tab.active {{ border-color: var(--cyan); color: var(--cyan); background: rgba(0,212,255,.08); }}
    .coin-panel {{ margin-top: 14px; border: 1px solid var(--green-line); padding: 14px; background: rgba(0,0,0,.3); }}
    .coin-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex-shrink: 0; margin-right: 6px; }}
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
    .legal-text {{ font-size: 13px; line-height: 1.8; color: var(--green-dim2); }}
    .legal-text h2 {{ color: var(--green); font-size: 14px; margin: 22px 0 8px; }}
    .legal-text p {{ margin: 0 0 12px; }}
    .legal-text ul {{ margin: 0 0 12px; padding-left: 20px; }}
    .legal-text li {{ margin-bottom: 4px; }}
    .legal-text a {{ color: var(--cyan); }}
    .footer-links {{ margin-top: 18px; font-size: 11px; color: var(--green-mute); }}
    .footer-links a {{ color: var(--green-mute); text-decoration: underline; }}
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
