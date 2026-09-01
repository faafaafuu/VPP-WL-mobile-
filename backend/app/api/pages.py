from __future__ import annotations

import json
from decimal import Decimal
from html import escape
from typing import Any

from app.domain.models import CommercialSubscription
from app.domain.tariffs import Tariff
from app.domain.wallet_connect import WALLET_ICONS

# Tariff card variants from design_handoff_vpn_landing v1.1: the default
# cyan card, a yellow "выгоднее" card, then the green highlighted "лучший
# выбор" card. A fourth tariff falls back to the default card again.
_TARIFF_VARIANTS = ("", "tariff--warn", "tariff--best", "")


def landing_page(tariffs: tuple[Tariff, ...]) -> str:
    base_monthly = _base_monthly_price(tariffs)
    rows = "\n".join(_tariff_row(i, tariff, base_monthly) for i, tariff in enumerate(tariffs))
    return _page(
        "Клео",
        f"""
        <section class="section" style="gap:var(--s6)">
          <div class="log">
            <div class="dim">root@core:~$ nmap -sV target.net</div>
            <div class="c-cyan">[+] host up <span class="dim">0.014s latency</span></div>
            <div class="c-cyan">[+] 443/tcp <span class="c-green">open</span> <span class="dim">encrypted</span></div>
            <div class="c-red">[!] traffic obfuscation <span class="c-green">ENABLED</span></div>
            <div class="dim">root@core:~$ ./vpn_router --start</div>
          </div>
          <div class="hero">
            <h1>БЫСТРЫЙ_VPN<br>_ДОСТУП<span class="cursor"></span></h1>
            <div class="subhead">
              <div>// YouTube · Telegram · Instagram · ChatGPT</div>
              <div>// подключение — 60 сек., без логов</div>
            </div>
            <a class="cta" href="#pricing">$ выбрать_тариф --run</a>
          </div>
        </section>

        <section class="section" id="pricing">
          <div class="section__label">// тарифы</div>
          <div class="tariffs">
            {rows}
          </div>
        </section>

        <section class="section">
          <div class="section__label">// как это работает</div>
          <div class="steps">
            <div class="step">
              <div class="step__n c-cyan">01.</div>
              <div class="step__text">оплата криптовалютой или картой</div>
            </div>
            <div class="step">
              <div class="step__n c-yellow">02.</div>
              <div class="step__text">установка v2rayN / v2rayNG / Hiddify</div>
            </div>
            <div class="step">
              <div class="step__n c-red">03.</div>
              <div class="step__text">ссылка приходит после подтверждения</div>
            </div>
          </div>
        </section>

        <div class="notes">
          <div>// уже оплатили, но потеряли ссылку? <a href="/recover">восстановить доступ</a></div>
          <div>// оплачивая тариф, вы принимаете <a href="/terms">публичную оферту</a> и <a href="/privacy">политику конфиденциальности</a></div>
        </div>
        <div class="payment-badge">
          <a href="https://freekassa.net" title="big-dark-1" target="_blank" rel="noopener"><img src="https://cdn.freekassa.net/images/logos/banners/f/big-dark-1.png" alt="big-dark-1" loading="lazy"></a>
        </div>
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
    renew_base_monthly = _base_monthly_price(tariffs)
    renew_rows = "\n".join(_tariff_row(i, tariff, renew_base_monthly) for i, tariff in enumerate(tariffs))
    if subscription.is_active():
        expires = subscription.expires_at.strftime("%d.%m.%Y") if subscription.expires_at else ""
        status = f"""
          <div class="block block-green">
            <div class="dim">root@core:~$ ./vpn_router --status</div>
            <h1 class="small">Ваш VPN активен<span class="cursor"></span></h1>
            <div class="subhead">// действует до {escape(expires)}<br>// сохраните адрес этой страницы — потеряли? <a href="/recover">восстановить по email</a></div>
            <div class="actions">
              <button class="cta" type="button" onclick="connectClient()">$ подключить --run</button>
              <button class="btn" type="button" onclick="copySub()">Скопировать ссылку</button>
              <button class="btn" type="button" onclick="toggleQr()">Показать QR</button>
              <button class="btn" type="button" onclick="copySingbox()">Ссылка для мобильного</button>
            </div>
            <p class="mono-box" id="subUrl">{escape(subscription_url)}</p>
            <p class="hint dim2">// «Ссылка для мобильного» — профиль с собственным DNS внутри туннеля. Берите её, если на мобильном интернете сайты не открываются или грузятся через раз.</p>
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
        "Клео — подключение",
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
          const singboxUrl = subUrl + '/singbox';
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
          async function copySingbox() {{
            const ok = await copyText(singboxUrl);
            const hint = document.getElementById('connectHint');
            hint.hidden = false;
            hint.textContent = ok
              ? 'Скопировано. Добавьте как новый профиль в Hiddify или sing-box — DNS пойдёт внутри туннеля.'
              : 'Не удалось скопировать. Откройте вручную: ' + singboxUrl;
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
    coin_options: list[dict[str, Any]],
    telegram_link: str | None = None,
    card_error: str | None = None,
) -> str:
    saved_email = subscription.customer_email or ""
    tg_bound = bool((subscription.tg_chat_id or "").strip())
    has_contact = bool(saved_email.strip()) or tg_bound
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
                "pay": opt.get("pay"),
                "pay_uri": opt.get("pay_uri"),
                "pay_units": opt.get("pay_units"),
                "wallets": opt.get("wallets") or [],
                "pay_qr_url": opt.get("pay_qr_url"),
            }
            for opt in coin_options
        ],
        ensure_ascii=False,
    )
    coin_blocks = "\n".join(_coin_block(i, opt, token) for i, opt in enumerate(coin_options))
    payment_methods, default_idx = _payment_method_section(coin_options)

    tg_button = (
        f'<a class="btn btn--cyan" id="tgBind" href="{escape(telegram_link)}" target="_blank" rel="noopener">'
        f'✈ привязать Telegram</a>'
        if telegram_link
        else ""
    )
    card_note = (
        f'<div class="callout callout--red" id="cardError">{escape(card_error)}</div>'
        if card_error
        else ""
    )
    contact_state = (
        '<p class="hint c-green" id="contactState">'
        + ("Telegram привязан — ссылку пришлём в чат." if tg_bound else f"Email сохранён: {escape(saved_email)}")
        + "</p>"
        if has_contact
        else '<p class="hint" id="contactState" hidden></p>'
    )
    locked_attr = "" if has_contact else " hidden"

    return _page(
        "Оплата заказа",
        f"""
        <section class="section" style="gap:var(--s4)">
          <div class="log">
            <div class="dim">root@core:~$ ./vpn_router --pay</div>
            <a class="order__back" href="/#pricing">&larr; сменить тариф</a>
          </div>
          <div class="order__head">
            <h1 class="small">{escape(tariff.title)}</h1>
            <dl class="order__meta">
              <dt>стоимость</dt><dd>{escape(price_rub)}</dd>
              <dt>заказ</dt><dd class="code">{escape(order_ref)}</dd>
            </dl>
          </div>
        </section>

        <section class="section" id="contactStep">
          <div class="section__head">
            <div class="section__label">// шаг 1 — куда прислать доступ</div>
            <div class="section__hint">без этого ключ будет некому отдать</div>
          </div>
          <div class="panel contact">
            <div class="log">
              <div class="dim">root@core:~$ ./vpn_router --bind contact</div>
              <div class="dim">// оплата анонимна, но получатель ключа должен быть известен —
                иначе после оплаты вернуть доступ можно будет только по этой вкладке</div>
            </div>
            <div class="contact__row">
              <input class="field" type="email" id="contactEmail" placeholder="you@example.com"
                     value="{escape(saved_email)}" autocomplete="email" inputmode="email">
              <button class="btn" type="button" onclick="saveEmail()">сохранить email</button>
            </div>
            <div class="contact__or">— или —</div>
            <div class="actions">{tg_button}</div>
            {contact_state}
          </div>
        </section>

        <div id="paySteps"{locked_attr}>
          <section class="section">
            <div class="section__head">
              <div class="section__label">// шаг 2 — способ оплаты</div>
              <div class="section__hint">выберите валюту и сеть</div>
            </div>
            <div class="payment-methods" id="coinTabs">
              {payment_methods}
              <div class="paygroup">
                <div class="paygroup__label">банковская карта</div>
                {card_note}
                <div class="card-pay">
                  <a class="btn btn--cyan" href="/invoice/{escape(token)}/freekassa/pay">оплатить картой</a>
                  <div class="card-brands"><span>VISA</span><span>MASTERCARD</span><span>МИР</span></div>
                </div>
              </div>
            </div>
          </section>

          <section class="section">
            <div class="section__label">// шаг 3 — перевод</div>
            {coin_blocks}
            <div class="callout" id="watchState">ожидание выбора валюты…</div>
          </section>

          <section class="section">
            <div class="section__label">// инструкция</div>
            <div class="panel howto">
              <ol>
                <li>Нажмите <b>$ подключить_кошелёк</b> — сумма, адрес и сеть подставятся сами,
                    вам останется подтвердить перевод в кошельке.</li>
                <li>Нет подключаемого кошелька? Скопируйте адрес и переведите вручную с биржи
                    (Binance, OKX, Bybit) — обязательно в той же <b>сети</b>.</li>
                <li>Переводите <b>точную сумму</b> — без округления, до последнего знака.</li>
                <li>После подтверждения в сети доступ включится автоматически — страница обновится сама.</li>
              </ol>
            </div>
          </section>

          <section class="section">
            <div class="section__label">// после оплаты</div>
            <div class="actions">
              <a class="btn" href="/connect/{escape(token)}">проверить статус доступа</a>
            </div>
            <div class="section__hint">// ссылка придёт на указанный контакт сразу после подтверждения оплаты</div>
          </section>
        </div>

        <div class="sheet" id="walletSheet" hidden>
          <div class="sheet__box">
            <div class="sheet__head">
              <span>выберите кошелёк</span>
              <button class="sheet__x" type="button" onclick="closeWalletSheet()" aria-label="закрыть">&#10005;</button>
            </div>
            <div class="sheet__list" id="walletList"></div>
            <p class="hint" id="walletHint" hidden></p>
          </div>
        </div>

        <div class="notes">
          <div>// сохраните ссылку на эту страницу — по ней вы всегда вернётесь к заказу</div>
          <div>// потеряли? <a href="/recover">восстановить доступ по email</a></div>
        </div>
        <script>
{_invoice_script(coins_js, token, default_idx if default_idx is not None else 0, has_contact)}
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


def freekassa_result_page(success: bool, support_email: str | None = None) -> str:
    contact = escape(support_email) if support_email else "поддержку"
    if success:
        return _page(
            "Оплата получена",
            f"""
            <div class="block block-green">
              <div class="dim">root@core:~$ ./vpn_router --freekassa --status</div>
              <h1 class="small">Оплата получена<span class="cursor"></span></h1>
              <div class="subhead">// доступ активируется в течение пары минут<br>// если привязали Telegram — ссылка придёт туда автоматически<br>// не пришла? напишите нам на {contact}, укажите время и сумму оплаты</div>
              <a class="cta" href="/recover">$ восстановить_по_email --run</a>
            </div>
            """,
        )
    return _page(
        "Оплата не прошла",
        f"""
        <div class="block block-red">
          <div class="dim">root@core:~$ ./vpn_router --freekassa --status</div>
          <h1 class="small c-red">Оплата не прошла</h1>
          <div class="subhead">// деньги не списаны — попробуйте ещё раз или выберите другой способ оплаты</div>
          <a class="cta" href="/#pricing">$ выбрать_тариф --run</a>
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
    variant = _TARIFF_VARIANTS[idx % len(_TARIFF_VARIANTS)]
    variant_cls = f" {variant}" if variant else ""
    months = max(tariff.duration_days // 30, 1)
    badge = f' <span class="badge">// {escape(tariff.badge)}</span>' if tariff.badge else ""
    price = Decimal(tariff.price_rub)
    per_month = f"{escape(_price(f'{(price / months):.2f}'))}/мес"

    price_block = f'<span class="price">{escape(_price(tariff.price_rub))}</span>'
    badge_block = "<span></span>"
    if base_monthly is not None and months > 1:
        full_price = base_monthly * months
        if full_price > price:
            discount_pct = round((1 - price / full_price) * 100)
            price_block = (
                f'<span class="price-old">{escape(_price(f"{full_price:.2f}"))}</span>'
                f'<span class="price">{escape(_price(tariff.price_rub))}</span>'
            )
            badge_block = f'<span class="tariff-badge">-{discount_pct}%</span>'

    return f"""
      <form method="post" action="/checkout" class="tariff-form">
        <input type="hidden" name="tariff_id" value="{escape(tariff.id)}">
        <button class="tariff{variant_cls}" type="submit">
          <span class="tariff-info">
            <span class="tariff-name">[{months:02d}] {escape(tariff.title)}{badge}</span>
            <span class="tariff-permo">{per_month}</span>
          </span>
          <span class="tariff-price-block">{price_block}</span>
          {badge_block}
        </button>
      </form>
    """


def _payment_method_section(coin_options: list[dict[str, Any]]) -> tuple[str, int | None]:
    """Payment-method picker matching the cyberpunk-theme handoff: a
    stablecoin toggle (USDT/USDC) with one shared "сеть" dropdown that
    switches to whichever stablecoin is active, a separate grid for
    single-network coins (ETH/BTC/TON/SOL), and the card-payment row.
    Returns (html, default selected index) — the default prefers USDT's
    ERC20 network, falling back to the first coin option available."""
    indexed = list(enumerate(coin_options))
    by_id = {opt["id"]: (i, opt) for i, opt in indexed}

    def network_select(prefix: str, elem_id: str, visible: bool) -> tuple[str, int | None]:
        entries = [(i, opt) for i, opt in indexed if opt["id"].startswith(prefix)]
        if not entries:
            return "", None
        default_i = next((i for i, opt in entries if opt["network_label"].startswith("ERC20")), entries[0][0])
        options = "\n".join(
            f'<option value="{i}"{" selected" if i == default_i else ""}>{escape(opt["network_label"])}</option>'
            for i, opt in entries
        )
        hidden_attr = "" if visible else " hidden"
        color = entries[0][1]["color"]
        label = "USDT" if prefix.startswith("usdt") else "USDC"
        html = (
            f'<div class="coin-group-dropdown" id="{elem_id}"{hidden_attr}>'
            f'<div class="coin-group-label"><span class="coin-dot" style="background:{escape(color)}"></span>{escape(label)}</div>'
            f'<select class="coin-select network-select" id="{elem_id}Select" onchange="selectCoin(parseInt(this.value))">{options}</select>'
            f'</div>'
        )
        return html, default_i

    def stable_button(prefix: str, label: str, active: bool) -> str:
        entries = [opt for opt in coin_options if opt["id"].startswith(prefix)]
        color = entries[0]["color"] if entries else "#fff"
        active_cls = " is-active" if active else ""
        return (
            f'<button type="button" class="coin{active_cls}" data-stable="{prefix.rstrip("_")}" onclick="selectStable(\'{prefix.rstrip("_")}\')">'
            f'<span class="coin-dot" style="background:{escape(color)}"></span>{escape(label)}'
            f'</button>'
        )

    def chip_html(coin_id: str) -> str:
        entry = by_id.get(coin_id)
        if entry is None:
            return ""
        i, opt = entry
        return (
            f'<button type="button" class="coin" data-idx="{i}" onclick="selectCoin({i})">'
            f'<span class="coin-dot" style="background:{escape(opt["color"])}"></span>'
            f'{escape(opt["label"])}'
            f'</button>'
        )

    usdt_select, usdt_default = network_select("usdt_", "networkRowUsdt", visible=True)
    usdc_select, usdc_default = network_select("usdc_", "networkRowUsdc", visible=False)
    default_idx = usdt_default if usdt_default is not None else usdc_default

    other_chips = "".join(chip_html(c) for c in ("eth", "btc", "ton", "sol"))

    html = f"""
      <div class="paygroup">
        <div class="paygroup__label">стейблкоины</div>
        <div class="coins coins--2" id="stableCoins">
          {stable_button("usdt_", "USDT", True)}
          {stable_button("usdc_", "USDC", False)}
        </div>
      </div>
      {usdt_select}
      {usdc_select}
      <div class="paygroup">
        <div class="paygroup__label">другая криптовалюта</div>
        <div class="coins coins--4">{other_chips}</div>
      </div>
    """
    return html, default_idx


def _coin_block(idx: int, opt: dict[str, Any], token: str) -> str:
    connect_btn = (
        f'<button class="cta" type="button" onclick="payWithWallet({idx})">$ подключить_кошелёк</button>'
        if opt.get("pay")
        else ""
    )
    return f"""
      <div class="coin-panel transfer" id="coinPanel{idx}" hidden>
        <div>
          <div class="transfer__coin">
            <span class="coin-dot" style="background:{escape(opt['color'])}"></span>
            <span class="c-white">{escape(opt['label'])}</span>
            <span class="net">{escape(opt['network_label'])}</span>
          </div>
          <p class="transfer__amount" id="amount{idx}" onclick="copyAmount({idx})">{escape(opt['amount'])} {escape(opt['label'])}</p>
        </div>
        <div class="field-group">
          <p class="field__label">адрес кошелька</p>
          <p class="field__value" id="addr{idx}">{escape(opt['address'])}</p>
        </div>
        <div class="transfer__actions">
          {connect_btn}
          <button class="btn" type="button" onclick="copyAddr({idx})">скопировать адрес</button>
          <button class="btn" type="button" onclick="toggleQr({idx})">QR-код</button>
        </div>
        <div class="qr-wrap" id="addrQr{idx}" hidden>
          <img src="/invoice/{escape(token)}/qr/{escape(opt['id'])}" alt="QR {escape(opt['label'])} {escape(opt['network_label'])}">
        </div>
        <p class="hint c-green" id="copyHint{idx}" hidden>Адрес скопирован.</p>
      </div>
    """


# The invoice page's client script. Kept out of the f-string above so the JS
# can use ordinary braces instead of doubling every one of them.
_INVOICE_JS = r"""
          const COINS = __COINS__;
          const TOKEN = __TOKEN__;
          let hasContact = __HAS_CONTACT__;
          let selectedIdx = null;
          let pollTimer = null;

          /* ---------- контакт ---------- */

          function unlockPayment() {
            hasContact = true;
            const steps = document.getElementById('paySteps');
            if (steps && steps.hidden) {
              steps.hidden = false;
              selectCoin(selectedIdx === null ? __DEFAULT_IDX__ : selectedIdx);
            }
          }
          function setContactState(text, cls) {
            const el = document.getElementById('contactState');
            if (!el) return;
            el.hidden = false;
            el.className = 'hint ' + cls;
            el.textContent = text;
          }
          async function saveEmail() {
            const input = document.getElementById('contactEmail');
            try {
              const resp = await fetch('/invoice/' + TOKEN + '/contact', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: input.value}),
              });
              if (resp.ok) {
                setContactState('Email сохранён — сюда придёт ссылка, по нему же работает восстановление.', 'c-green');
                unlockPayment();
              } else {
                setContactState('Проверьте адрес — похоже, в нём опечатка.', 'c-red');
              }
            } catch (e) {
              setContactState('Не удалось сохранить — попробуйте ещё раз.', 'c-red');
            }
          }

          /* ---------- выбор монеты ---------- */

          function selectStable(stable) {
            const select = document.getElementById('networkRow' + (stable === 'usdt' ? 'Usdt' : 'Usdc') + 'Select');
            if (select) selectCoin(parseInt(select.value));
          }

          async function selectCoin(idx) {
            selectedIdx = idx;
            const coin = COINS[idx];
            const isStable = coin.id.startsWith('usdt_') || coin.id.startsWith('usdc_');
            document.querySelectorAll('.coin-panel').forEach((p, i) => p.hidden = i !== idx);
            document.querySelectorAll('.coin[data-stable]').forEach(b => {
              b.classList.toggle('is-active', isStable && coin.id.startsWith(b.dataset.stable + '_'));
            });
            document.querySelectorAll('.coin[data-idx]').forEach(b => {
              b.classList.toggle('is-active', !isStable && parseInt(b.dataset.idx) === idx);
            });
            document.querySelectorAll('.network-select').forEach(s => {
              if ([...s.options].some(o => parseInt(o.value) === idx)) s.value = idx;
            });
            const rowUsdt = document.getElementById('networkRowUsdt');
            const rowUsdc = document.getElementById('networkRowUsdc');
            if (rowUsdt) rowUsdt.hidden = !coin.id.startsWith('usdt_');
            if (rowUsdc) rowUsdc.hidden = !coin.id.startsWith('usdc_');
            const state = document.getElementById('watchState');
            if (!hasContact) {
              state.textContent = 'сначала укажите email или привяжите Telegram — иначе ссылку будет некуда прислать';
              return;
            }
            try {
              const resp = await fetch('/invoice/' + TOKEN + '/select', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({coin_id: COINS[idx].id}),
              });
              const data = await resp.json();
              if (data.status === 'active') { window.location = data.connect_url; return; }
              if (data.amount) {
                COINS[idx].amount = data.amount;
                COINS[idx].address = data.address;
                /* Ссылка на перевод и её QR зависят от точной суммы, которая
                   становится известна только здесь. */
                COINS[idx].pay_uri = data.pay_uri;
                COINS[idx].pay_units = data.pay_units;
                COINS[idx].pay_qr_url = data.pay_qr_url;
                COINS[idx].wallets = data.wallets || [];
                document.getElementById('amount' + idx).textContent = data.amount + ' ' + COINS[idx].label;
                document.getElementById('addr' + idx).textContent = data.address;
                state.textContent = 'переведите ровно ' + data.amount + ' ' + COINS[idx].label +
                  ' — доступ включится автоматически после подтверждения сети';
                startPolling();
              }
            } catch (e) {
              state.textContent = 'не удалось получить сумму — обновите страницу';
            }
          }

          function startPolling() {
            if (pollTimer) return;
            pollTimer = setInterval(async () => {
              try {
                const resp = await fetch('/invoice/' + TOKEN + '/status');
                const data = await resp.json();
                if (data.status === 'active') {
                  clearInterval(pollTimer);
                  window.location = data.connect_url;
                  return;
                }
                /* Telegram могли привязать в другой вкладке — открываем оплату сразу. */
                if (data.contact && !hasContact) {
                  setContactState(data.contact_telegram
                    ? 'Telegram привязан — ссылку пришлём в чат.'
                    : 'Email сохранён: ' + data.contact_email, 'c-green');
                  unlockPayment();
                }
              } catch (e) {}
            }, 5000);
          }

          /* ---------- копирование ---------- */

          async function copyText(text) {
            if (navigator.clipboard && window.isSecureContext) {
              try { await navigator.clipboard.writeText(text); return true; } catch (e) {}
            }
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            let ok = false;
            try { ok = document.execCommand('copy'); } catch (e) {}
            document.body.removeChild(ta);
            return ok;
          }
          async function copyAddr(idx) {
            await copyText(COINS[idx].address);
            const hint = document.getElementById('copyHint' + idx);
            if (hint) hint.hidden = false;
          }
          async function copyAmount(idx) { await copyText(COINS[idx].amount); }
          function toggleQr(idx) {
            const qr = document.getElementById('addrQr' + idx);
            if (qr) qr.hidden = !qr.hidden;
          }

          /* ---------- подключение кошелька ---------- */

          const WALLET_ICONS = __WALLET_ICONS__;

          /* Кнопка кошелька: ссылка уже несёт сумму, адрес и сеть. Если
             приложения на устройстве нет, схему некому обработать и ничего
             не откроется — поэтому через полторы секунды показываем подсказку
             с QR вместо молчания. */
          function addWalletButtons(coin) {
            const list = coin.wallets || [];
            if (!list.length) return false;
            const group = sheetGroup('оплатить в кошельке');
            list.forEach(function (w) {
              /* Именно <a href>, а не обработчик с location.href: переход на
                 схему вроде solana: или bitcoin: из скрипта браузеры глушат
                 как навигацию на неизвестный протокол, и нажатие просто
                 ничего не делает. По ссылке с жестом пользователя — открывает. */
              const row = walletRow(group, w.name, WALLET_ICONS[w.id] || '', w.url);
              row.addEventListener('click', function () { notInstalledLater(w.name); });
            });
            return true;
          }

          let openedHintTimer = null;
          function notInstalledLater(name) {
            if (openedHintTimer) clearTimeout(openedHintTimer);
            /* Открылся кошелёк или нет — со страницы не видно. Раньше здесь
               утверждалось, что приложения нет: неправда ровно в том случае,
               когда оно есть, а схему просто некому обработать. */
            openedHintTimer = setTimeout(function () {
              walletMsg('Открываем ' + name + '. Если окно не появилось — ' +
                        'выберите другой кошелёк или отсканируйте QR ниже.', '');
            }, 1500);
          }

          function addQr(coin) {
            if (!coin.pay_qr_url) return;
            const group = sheetGroup('оплатить с другого устройства');
            const qr = document.createElement('div');
            qr.className = 'qr-wrap sheet__qr';
            qr.hidden = true;
            const img = document.createElement('img');
            img.src = coin.pay_qr_url + '?v=' + encodeURIComponent(coin.amount);
            img.alt = 'QR перевода';
            qr.appendChild(img);
            walletRow(group, 'показать QR перевода', '', function () { qr.hidden = !qr.hidden; });
            group.appendChild(qr);
          }

          function addManual(coin) {
            const group = sheetGroup('перевод вручную');
            walletRow(group, 'скопировать адрес', '', function () {
              copyText(coin.address);
              walletMsg('Адрес скопирован. Переводите ровно ' + coin.amount + ' ' + coin.label + '.', 'c-green');
            });
          }

          function payWithWallet(idx) {
            const coin = COINS[idx];
            const spec = coin.pay;
            document.getElementById('walletList').textContent = '';
            openWalletSheet();
            if (!spec) {
              walletMsg('Для этой сети автоперевод недоступен — скопируйте адрес и сумму.', 'c-red');
              return;
            }
            if (spec.kind === 'evm') { buildEvmSheet(coin, spec); return; }
            if (spec.kind === 'tron') { buildTronSheet(coin, spec); return; }
            buildUriSheet(coin);
          }

          function buildEvmSheet(coin, spec) {
            const wallets = discoverEvmWallets();
            if (wallets.length) {
              /* Кошелёк есть прямо здесь — подписываем перевод на странице,
                 ссылки на мобильные приложения расширению слать некуда. */
              const group = sheetGroup('кошелёк в этом браузере');
              wallets.forEach(function (w) {
                walletRow(group, w.info.name, w.info.icon, function () { evmSend(w.provider, coin, spec); });
              });
              addQr(coin);
              walletMsg('Выберите кошелёк — сумма, адрес и сеть подставятся автоматически.', '');
              return;
            }
            addWalletButtons(coin);
            addQr(coin);
            walletMsg('Выберите кошелёк — он откроется сразу на экране отправки, сумма и адрес уже подставлены.', '');
          }

          function buildTronSheet(coin, spec) {
            const tronReady = !!((window.tronLink && window.tronLink.tronWeb) || window.tronWeb);
            if (tronReady) {
              const group = sheetGroup('кошелёк в этом браузере');
              walletRow(group, 'TronLink', '', function () { payViaTron(coin, spec); });
            }
            addManual(coin);
            walletMsg(tronReady
              ? 'TronLink подставит сумму и адрес сам — останется подтвердить.'
              : 'У TRC20 нет платёжной ссылки, а TronLink подключается только расширением в браузере. С телефона переведите вручную: адрес ниже, сумма ровно ' + coin.amount + ' ' + coin.label + '.', '');
          }

          /* Расширения Solana-кошельков не регистрируют схему solana: —
             они инжектят провайдер. Поэтому на десктопе ссылка молчит, и
             говорить при этом "кошелька нет" было неправдой: он есть,
             обращаться к нему надо иначе. */
          function solanaProviders() {
            const found = [];
            const phantom = window.phantom && window.phantom.solana;
            if (phantom && phantom.isPhantom) found.push({name: 'Phantom', id: 'phantom', provider: phantom});
            if (window.solflare && window.solflare.isSolflare) {
              found.push({name: 'Solflare', id: 'solflare', provider: window.solflare});
            }
            if (window.backpack && window.backpack.isBackpack) {
              found.push({name: 'Backpack', id: 'backpack', provider: window.backpack});
            }
            return found;
          }

          /* Ключи — коды, которые возвращает /solana/tx. Текст живёт здесь,
             чтобы покупателю не показывали служебную строку на английском. */
          const SOLANA_ERRORS = {
            'same_account': 'Подключён тот самый кошелёк, на который идёт оплата — перевести самому себе нельзя. ' +
                            'Переключитесь в кошельке на другой счёт и нажмите ещё раз.',
            'contact required': 'Сначала укажите email или привяжите Telegram.',
            'missing sender': 'Кошелёк не выдал адрес счёта — переподключитесь и попробуйте ещё раз.',
            'select the coin first': 'Сумма ещё не зафиксирована — подождите пару секунд и повторите.',
            'amount unavailable': 'Курс сейчас недоступен — обновите страницу через минуту.',
            'coin not configured': 'Оплата в SOL временно недоступна — выберите другую валюту.',
            'solana rpc unavailable': 'Сеть Solana сейчас не отвечает — попробуйте через минуту или отсканируйте QR.',
            'build_failed': 'Сеть Solana сейчас не отвечает — попробуйте через минуту или отсканируйте QR.',
          };

          async function solanaSend(entry, coin) {
            try {
              walletMsg('Подтвердите подключение в ' + entry.name + '…', '');
              const res = await entry.provider.connect();
              const from = (res && res.publicKey ? res.publicKey : entry.provider.publicKey);
              if (!from) { walletMsg('Кошелёк не выдал адрес — попробуйте ещё раз.', 'c-red'); return; }
              walletMsg('Готовим перевод…', '');
              const resp = await fetch('/invoice/' + TOKEN + '/solana/tx', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({from: from.toString()}),
              });
              const data = await resp.json();
              if (!resp.ok || !data.message) {
                walletMsg(SOLANA_ERRORS[data.error] ||
                  'Не удалось собрать перевод — попробуйте ещё раз или отсканируйте QR.', 'c-red');
                return;
              }
              walletMsg('Подтвердите перевод в ' + entry.name + '…', '');
              const sent_ = await entry.provider.request({
                method: 'signAndSendTransaction',
                params: {message: data.message},
              });
              sent((sent_ && (sent_.signature || sent_)) || '', coin.pay);
            } catch (e) {
              walletMsg(walletError(e), 'c-red');
            }
          }

          function buildUriSheet(coin) {
            if (coin.id === 'sol') {
              const injected = solanaProviders();
              if (injected.length) {
                const group = sheetGroup('кошелёк в этом браузере');
                injected.forEach(function (entry) {
                  walletRow(group, entry.name, WALLET_ICONS[entry.id] || '', function () {
                    solanaSend(entry, coin);
                  });
                });
                addQr(coin);
                walletMsg('Выберите кошелёк — счёт для оплаты выбираете в нём сами, сумма и получатель подставятся.', '');
                return;
              }
            }
            addWalletButtons(coin);
            addQr(coin);
            walletMsg('Выберите кошелёк — он откроется сразу на экране отправки, сумма и адрес уже подставлены.', '');
          }

          /* Десятичная строка -> целое число минимальных единиц сети.
             Через BigInt, а не через Number: сумма вроде 0.00095238 в double
             округляется, и на счёт уходит не та величина, которую ждёт
             сверщик платежей. */
          function toUnits(amountStr, decimals) {
            const s = String(amountStr).trim().replace(',', '.');
            if (!/^\d+(\.\d+)?$/.test(s)) return null;
            const parts = s.split('.');
            const frac = ((parts[1] || '') + '0'.repeat(decimals)).slice(0, decimals);
            return BigInt(parts[0] + frac);
          }
          function padWord(hex) {
            return hex.replace(/^0x/, '').toLowerCase().padStart(64, '0');
          }

          function walletMsg(text, cls) {
            const hint = document.getElementById('walletHint');
            hint.hidden = false;
            hint.className = 'hint ' + (cls || '');
            hint.textContent = text;
          }
          function openWalletSheet() { document.getElementById('walletSheet').hidden = false; }
          function closeWalletSheet() {
            document.getElementById('walletSheet').hidden = true;
            document.getElementById('walletHint').hidden = true;
          }

          /* EIP-6963: кошельки сами объявляют о себе, поэтому список получается
             настоящим — с их собственными названиями и логотипами, без
             угадывания window.ethereum и без гонки расширений. */
          const evmWallets = [];
          window.addEventListener('eip6963:announceProvider', function (event) {
            const detail = event.detail;
            if (!detail || !detail.info || evmWallets.some(w => w.info.uuid === detail.info.uuid)) return;
            evmWallets.push(detail);
          });
          window.dispatchEvent(new Event('eip6963:requestProvider'));
          function discoverEvmWallets() {
            window.dispatchEvent(new Event('eip6963:requestProvider'));
            const found = evmWallets.slice();
            if (!found.length && window.ethereum) {
              found.push({info: {uuid: 'injected', name: 'Кошелёк в браузере', icon: ''}, provider: window.ethereum});
            }
            return found;
          }

          function sheetGroup(label) {
            const wrap = document.createElement('div');
            wrap.className = 'sheet__group';
            const head = document.createElement('div');
            head.className = 'sheet__grouplabel';
            head.textContent = label;
            wrap.appendChild(head);
            document.getElementById('walletList').appendChild(wrap);
            return wrap;
          }
          function walletRow(parent, name, icon, action) {
            const el = document.createElement(typeof action === 'string' ? 'a' : 'button');
            el.className = 'wallet';
            if (typeof action === 'string') {
              el.href = action;
              el.rel = 'noopener';
              /* Обычная ссылка кошелька — в новую вкладку, чтобы страница
                 заказа осталась открытой. Схемы вроде solana: открываем в
                 текущей: в новой вкладке браузеры их блокируют. */
              if (/^https?:/i.test(action)) el.target = '_blank';
            } else {
              el.type = 'button';
              el.addEventListener('click', action);
            }
            if (icon) {
              const img = document.createElement('img');
              img.src = icon;
              img.alt = '';
              el.appendChild(img);
            }
            const span = document.createElement('span');
            span.textContent = name;
            el.appendChild(span);
            parent.appendChild(el);
            return el;
          }

          async function payViaTron(coin, spec) {
            walletMsg('Подключаемся к TronLink…', '');
            try {
              if (window.tronLink && window.tronLink.request) {
                await window.tronLink.request({method: 'tron_requestAccounts'});
              }
              const tronWeb = (window.tronLink && window.tronLink.tronWeb) || window.tronWeb;
              if (!tronWeb || !tronWeb.defaultAddress || !tronWeb.defaultAddress.base58) {
                walletMsg('TronLink не найден. Установите расширение или переведите вручную по адресу ниже.', 'c-red');
                return;
              }
              const units = toUnits(coin.amount, spec.token_decimals);
              if (units === null) { walletMsg('Сумма ещё не рассчитана — подождите пару секунд.', 'c-red'); return; }
              const contract = await tronWeb.contract().at(spec.contract);
              walletMsg('Подтвердите перевод в TronLink…', '');
              const txid = await contract.transfer(coin.address, units.toString()).send();
              sent(txid, spec);
            } catch (e) {
              walletMsg(walletError(e), 'c-red');
            }
          }

          async function evmSend(provider, coin, spec) {
            try {
              walletMsg('Подтвердите подключение в кошельке…', '');
              const accounts = await provider.request({method: 'eth_requestAccounts'});
              const from = accounts && accounts[0];
              if (!from) { walletMsg('Кошелёк не выдал адрес — попробуйте ещё раз.', 'c-red'); return; }
              const current = await provider.request({method: 'eth_chainId'});
              if (String(current).toLowerCase() !== spec.chain_hex) {
                walletMsg('Переключаем сеть на ' + spec.add_chain.chainName + '…', '');
                try {
                  await provider.request({method: 'wallet_switchEthereumChain', params: [{chainId: spec.chain_hex}]});
                } catch (switchError) {
                  /* 4902 — сеть кошельку неизвестна; добавляем и повторяем. */
                  if (switchError && switchError.code === 4902) {
                    await provider.request({method: 'wallet_addEthereumChain', params: [spec.add_chain]});
                  } else {
                    throw switchError;
                  }
                }
                /* Не всякий кошелёк действительно переключается: некоторые
                   отвечают успехом и остаются где были. Тогда перевод уходит
                   по адресу контракта, которого в текущей сети нет, и кошелёк
                   падает на симуляции газа с невнятным EVM-кодом. */
                const after = await provider.request({method: 'eth_chainId'});
                if (String(after).toLowerCase() !== spec.chain_hex) {
                  walletMsg('Кошелёк остался в другой сети. Переключите его на ' +
                            spec.add_chain.chainName + ' вручную и нажмите ещё раз.', 'c-red');
                  return;
                }
              }
              const units = toUnits(coin.amount, spec.token_decimals);
              if (units === null) { walletMsg('Сумма ещё не рассчитана — подождите пару секунд.', 'c-red'); return; }
              let tx;
              if (spec.contract) {
                /* transfer(address,uint256) */
                tx = {from: from, to: spec.contract,
                      data: '0xa9059cbb' + padWord(coin.address) + padWord(units.toString(16))};
              } else {
                tx = {from: from, to: coin.address, value: '0x' + units.toString(16)};
              }
              walletMsg('Подтвердите перевод в кошельке…', '');
              const hash = await provider.request({method: 'eth_sendTransaction', params: [tx]});
              sent(hash, spec);
            } catch (e) {
              walletMsg(walletError(e), 'c-red');
            }
          }

          function walletError(e) {
            if (e && (e.code === 4001 || e.code === 'ACTION_REJECTED')) return 'Перевод отменён в кошельке.';
            const msg = (e && (e.message || e.reason)) ? String(e.message || e.reason) : '';
            if (/insufficient|InvalidFEOpcode|execution reverted|gas required|out of gas/i.test(msg)) {
              return 'Кошелёк не смог собрать перевод — почти всегда это значит, ' +
                     'что на нём нет нужной суммы в этой сети или не хватает монеты на комиссию. ' +
                     'Проверьте баланс и сеть, либо выберите другую валюту.';
            }
            return 'Кошелёк вернул ошибку' + (msg ? ': ' + msg : '') + '. Можно перевести вручную по адресу ниже.';
          }

          function sent(hash, spec) {
            const list = document.getElementById('walletList');
            list.textContent = '';
            if (hash && spec.explorer_tx) {
              const group = sheetGroup('транзакция');
              walletRow(group, 'посмотреть в обозревателе', '', spec.explorer_tx + hash);
            }
            walletMsg('Перевод отправлен. Доступ включится сам, как только сеть подтвердит платёж — страницу можно не закрывать.', 'c-green');
            const state = document.getElementById('watchState');
            if (state) state.textContent = 'платёж отправлен — ждём подтверждения сети…';
            startPolling();
          }

          document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeWalletSheet();
          });
          document.getElementById('walletSheet').addEventListener('click', function (e) {
            if (e.target === this) closeWalletSheet();
          });

          selectCoin(__DEFAULT_IDX__);
          startPolling();
"""


def _invoice_script(coins_js: str, token: str, default_idx: int, has_contact: bool) -> str:
    return (
        _INVOICE_JS
        .replace("__COINS__", coins_js)
        .replace("__WALLET_ICONS__", json.dumps(WALLET_ICONS, ensure_ascii=False))
        .replace("__TOKEN__", json.dumps(token))
        .replace("__HAS_CONTACT__", "true" if has_contact else "false")
        .replace("__DEFAULT_IDX__", str(int(default_idx)))
    )


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
  <!-- Реклама VPN-сервисов в РФ запрещена с марта 2024 года, а в реестр
       блокировок домены попадают в том числе по находке в поисковой выдаче.
       Продажи идут из Telegram, поиск канал привлечения не даёт — поэтому
       страницы закрыты от индексации, а не переписаны под поисковик. -->
  <meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
  <meta name="description" content="Личный кабинет сервиса Клео.">
  <meta name="referrer" content="no-referrer">
  <link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2032%2032%22%3E%3Crect%20width%3D%2232%22%20height%3D%2232%22%20fill%3D%22%23050705%22%2F%3E%3Cg%20fill%3D%22none%22%20stroke%3D%22%2300ff41%22%20stroke-width%3D%222.2%22%20stroke-linecap%3D%22round%22%3E%3Ccircle%20cx%3D%2216%22%20cy%3D%2216%22%20r%3D%2210.5%22%2F%3E%3Cellipse%20cx%3D%2216%22%20cy%3D%2216%22%20rx%3D%224.6%22%20ry%3D%2210.5%22%2F%3E%3Cpath%20d%3D%22M5.5%2016h21M7.6%2010.2h16.8M7.6%2021.8h16.8%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050705;
      --green: #00ff41;
      --green-dim: rgba(0,255,65,.55);
      --green-dim2: rgba(0,255,65,.55);
      --green-mute: rgba(0,255,65,.35);
      --green-faint: rgba(0,255,65,.3);
      --line: rgba(0,255,65,.18);
      --line-soft: rgba(0,255,65,.12);
      --line-strong: rgba(0,255,65,.35);
      --green-line: rgba(0,255,65,.3);
      --panel: rgba(0,255,65,.02);
      --cyan: #00d4ff;
      --yellow: #ffd60a;
      --red: #ff2b4d;
      --white: #fff;
      --ink-on-green: #020402;

      --s1: 4px;  --s2: 8px;  --s3: 12px; --s4: 16px;
      --s5: 20px; --s6: 24px; --s8: 32px; --s10: 40px; --s12: 48px;

      --ctrl: 52px;
      --page: 840px;
      --pad: 40px;
      --font: 'Share Tech Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    /* Components below set display: flex/grid, which outranks the UA rule
       for [hidden] — without this every coin panel and both network rows
       render at once instead of only the selected one. */
    [hidden] {{ display: none !important; }}
    body {{
      margin: 0;
      background: var(--bg);
      background-image:
        linear-gradient(rgba(0,255,65,.028) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,65,.028) 1px, transparent 1px);
      background-size: 24px 24px;
      color: var(--green);
      font: 400 14px/1.5 var(--font);
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--cyan); text-decoration: none; }}
    a:hover {{ color: var(--green); }}

    .shell {{
      max-width: var(--page); margin: 0 auto; min-height: 100vh;
      border-left: 1px solid var(--line); border-right: 1px solid var(--line);
      display: flex; flex-direction: column;
    }}
    .chrome {{
      display: flex; align-items: center; justify-content: space-between; height: 48px;
      padding: 0 var(--s5); border-bottom: 1px solid rgba(0,255,65,.2);
      background: rgba(0,255,65,.03); position: sticky; top: 0; z-index: 10; backdrop-filter: blur(4px);
    }}
    .chrome__dots {{ display: flex; gap: var(--s2); }}
    .chrome__dots i {{ width: 10px; height: 10px; border-radius: 50%; display: block; }}
    .chrome__dots i:nth-child(1) {{ background: var(--red); }}
    .chrome__dots i:nth-child(2) {{ background: var(--yellow); }}
    .chrome__dots i:nth-child(3) {{ background: var(--green); }}
    .chrome__title {{ font-size: 11px; letter-spacing: .5px; color: rgba(0,255,65,.4); }}
    .main {{ flex: 1; padding: var(--pad); display: flex; flex-direction: column; gap: var(--s8); }}
    .statusbar {{
      display: flex; align-items: center; height: 44px; padding: 0 var(--pad);
      border-top: 1px dashed rgba(0,255,65,.2); font-size: 11px; letter-spacing: .5px; color: var(--green-faint);
    }}
    .statusbar b {{ color: var(--green); font-weight: 400; margin: 0 var(--s1); }}

    .section {{ display: flex; flex-direction: column; gap: 14px; }}
    .section__label {{ font-size: 10.5px; letter-spacing: 2px; text-transform: uppercase; color: var(--green-faint); }}
    .section__head {{ display: flex; align-items: baseline; justify-content: space-between; gap: var(--s4); }}
    .section__hint {{ font-size: 11.5px; color: var(--green-faint); }}
    .panel {{ padding: var(--s6) 28px; border: 1px solid rgba(0,255,65,.14); background: var(--panel); }}

    .syslog, .log {{ display: flex; flex-direction: column; gap: var(--s1); font-size: 12.5px; line-height: 1.7; }}
    .dim {{ color: rgba(0,255,65,.4); font-size: 12.5px; line-height: 1.7; }}
    .dim2 {{ color: rgba(0,255,65,.5); }}
    .c-cyan {{ color: var(--cyan); }}
    .c-yellow {{ color: var(--yellow); }}
    .c-red {{ color: var(--red); }}
    .c-green {{ color: var(--green); }}
    .c-white {{ color: var(--white); }}

    .hero {{ display: flex; flex-direction: column; gap: var(--s5); }}
    h1 {{
      margin: 0; font-size: 44px; line-height: 1.15; letter-spacing: -.5px; font-weight: 700;
      color: var(--green); text-shadow: 0 0 14px rgba(0,255,65,.45);
    }}
    h1.small {{ font-size: 32px; line-height: 1; }}
    .cursor {{
      display: inline-block; width: 14px; height: .82em; background: var(--green);
      margin-left: 4px; vertical-align: -.06em; animation: blink 1s steps(1) infinite;
    }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    .subhead {{ display: flex; flex-direction: column; gap: 6px; font-size: 13.5px; line-height: 1.6; color: var(--green-dim); overflow-wrap: anywhere; }}

    .btn, .cta {{
      display: inline-flex; align-items: center; justify-content: center; gap: var(--s2);
      height: var(--ctrl); padding: 0 28px; font: inherit; font-size: 13.5px; line-height: 1;
      border: 1px solid var(--line-strong); background: rgba(0,255,65,.03); color: var(--green);
      cursor: pointer; text-decoration: none; text-align: center;
      transition: background .15s, box-shadow .15s, filter .15s;
    }}
    .btn:hover {{ background: rgba(0,255,65,.08); color: var(--green); }}
    .cta {{
      background: var(--green); border-color: var(--green); color: var(--ink-on-green);
      font-weight: 700; box-shadow: 0 0 20px rgba(0,255,65,.3); align-self: flex-start;
    }}
    .cta:hover {{ filter: brightness(1.15); box-shadow: 0 0 28px rgba(0,255,65,.5); color: var(--ink-on-green); }}
    .btn--cyan {{ border-color: rgba(0,212,255,.45); background: rgba(0,212,255,.06); color: var(--cyan); }}
    .btn--cyan:hover {{ background: rgba(0,212,255,.14); color: var(--cyan); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: var(--s3); }}

    .tariffs {{ display: flex; flex-direction: column; gap: var(--s3); }}
    .tariff-form {{ margin: 0; }}
    .tariff {{
      width: 100%; display: grid; grid-template-columns: 1fr 110px 64px; align-items: center;
      gap: var(--s4); min-height: 64px; padding: 14px var(--s5);
      border: 1px solid rgba(0,212,255,.3); background: rgba(0,212,255,.04);
      font: inherit; text-align: left; cursor: pointer; color: inherit;
      transition: background .15s, box-shadow .15s;
    }}
    .tariff:hover {{ background: rgba(0,212,255,.1); }}
    .tariff-info {{ display: flex; flex-direction: column; gap: 5px; }}
    .tariff-name {{ font-size: 14px; color: var(--cyan); }}
    .badge {{ color: var(--green-mute); }}
    .tariff-permo {{ font-size: 11.5px; color: rgba(0,255,65,.4); }}
    .tariff-price-block {{ display: flex; align-items: baseline; justify-content: flex-end; gap: var(--s2); text-align: right; }}
    .price {{ font-size: 17px; font-weight: 700; color: var(--white); white-space: nowrap; }}
    .price-old {{ font-size: 12px; color: var(--green-faint); text-decoration: line-through; }}
    .tariff-badge {{
      justify-self: end; display: inline-flex; align-items: center; justify-content: center;
      width: 52px; height: 24px; background: rgba(255,43,77,.14);
      border: 1px solid rgba(255,43,77,.5); font-size: 11.5px; color: var(--red);
    }}
    .tariff--warn {{ border-color: rgba(255,214,10,.55); background: rgba(255,214,10,.05); }}
    .tariff--warn:hover {{ background: rgba(255,214,10,.1); }}
    .tariff--warn .tariff-name {{ color: var(--yellow); }}
    .tariff--best {{ border-color: var(--green); background: rgba(0,255,65,.07); box-shadow: 0 0 18px rgba(0,255,65,.12); }}
    .tariff--best:hover {{ background: rgba(0,255,65,.12); }}
    .tariff--best .tariff-name {{ color: var(--green); }}

    .steps {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s3); }}
    .step {{ display: flex; flex-direction: column; gap: var(--s3); padding: 18px; border: 1px solid rgba(0,255,65,.14); background: var(--panel); }}
    .step__n {{ font-size: 12px; }}
    .step__text {{ font-size: 13px; line-height: 1.5; color: rgba(0,255,65,.6); }}

    .notes {{
      display: flex; flex-direction: column; gap: var(--s2); padding-top: var(--s5);
      border-top: 1px solid var(--line-soft); font-size: 12px; line-height: 1.7; color: var(--green-mute);
    }}
    .footer-links {{ font-size: 12px; color: var(--green-mute); }}
    .footer-links a {{ color: rgba(0,255,65,.6); text-decoration: underline; }}

    .order__head {{
      display: flex; align-items: flex-end; justify-content: space-between; gap: var(--s6);
      padding-bottom: var(--s5); border-bottom: 1px solid rgba(0,255,65,.14);
    }}
    .order__meta {{ display: grid; grid-template-columns: auto auto; gap: 6px var(--s5); font-size: 12px; text-align: right; }}
    .order__meta dt {{ color: var(--green-faint); margin: 0; }}
    .order__meta dd {{ margin: 0; color: var(--white); }}
    .order__meta dd.code {{ color: var(--cyan); }}
    .order__back {{ color: var(--yellow); font-size: 12px; }}
    .order__back:hover {{ color: var(--yellow); text-decoration: underline; }}

    .paygroup {{ display: flex; flex-direction: column; gap: var(--s3); }}
    .paygroup__label {{ font-size: 10.5px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--green-faint); }}
    .payment-methods {{ display: flex; flex-direction: column; gap: var(--s4); }}
    .coins {{ display: grid; gap: var(--s3); }}
    .coins--2 {{ grid-template-columns: repeat(2, 1fr); }}
    .coins--4 {{ grid-template-columns: repeat(4, 1fr); }}
    .coin {{
      display: flex; align-items: center; gap: var(--s3); height: var(--ctrl); padding: 0 var(--s4);
      border: 1px solid var(--line); background: var(--panel); color: var(--green-dim);
      font: inherit; font-size: 13.5px; cursor: pointer;
      transition: background .15s, border-color .15s;
    }}
    .coin:hover {{ border-color: var(--line-strong); background: rgba(0,255,65,.05); color: var(--green); }}
    .coin.is-active {{ border-color: var(--green); background: rgba(0,255,65,.08); color: var(--green); }}
    .coin-dot {{ width: 8px; height: 8px; border-radius: 50%; flex: none; display: block; }}

    .coin-group-dropdown {{ display: flex; align-items: center; gap: var(--s3); flex-wrap: wrap; }}
    .coin-group-label {{
      display: flex; align-items: center; gap: var(--s2); min-width: 62px;
      font-size: 13.5px; color: var(--white);
    }}
    .coin-select {{
      appearance: none; flex: 1; min-width: 0; height: var(--ctrl); padding: 0 var(--s5) 0 var(--s4);
      border: 1px solid var(--line); background: rgba(0,0,0,.35); color: var(--green);
      font: inherit; font-size: 13.5px; cursor: pointer;
      background-image: linear-gradient(45deg, transparent 50%, rgba(0,255,65,.5) 50%),
                        linear-gradient(135deg, rgba(0,255,65,.5) 50%, transparent 50%);
      background-position: calc(100% - 14px) center, calc(100% - 9px) center;
      background-size: 5px 5px, 5px 5px; background-repeat: no-repeat;
    }}
    .coin-select:hover {{ border-color: var(--line-strong); }}
    .coin-select:focus {{ outline: none; border-color: var(--cyan); }}

    .card-pay {{
      display: grid; grid-template-columns: 1fr auto; align-items: center; gap: var(--s4);
      padding: var(--s4) var(--s5); border: 1px solid rgba(0,255,65,.14); background: var(--panel);
    }}
    .card-pay .btn {{ justify-self: start; }}
    .card-brands {{ display: flex; gap: var(--s2); }}
    .card-brands span {{
      display: inline-flex; align-items: center; justify-content: center; height: 28px; padding: 0 10px;
      border: 1px solid rgba(0,212,255,.35); font-size: 10.5px; letter-spacing: .5px; color: rgba(0,212,255,.8);
    }}

    .transfer {{
      display: flex; flex-direction: column; gap: var(--s6); padding: 28px;
      border: 1px solid var(--green); background: rgba(0,255,65,.05); box-shadow: 0 0 24px rgba(0,255,65,.1);
    }}
    .transfer__coin {{ display: flex; align-items: center; gap: var(--s3); font-size: 11.5px; }}
    .transfer__coin .net {{ color: var(--green-faint); }}
    .transfer__amount {{ font-size: 34px; line-height: 1; font-weight: 700; color: var(--white); letter-spacing: -.5px; margin: 10px 0 0; cursor: pointer; }}
    .field-group {{ display: flex; flex-direction: column; gap: var(--s2); }}
    .field__label {{ font-size: 10.5px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--green-faint); margin: 0; }}
    .field__value {{
      display: flex; align-items: center; min-height: 48px; padding: 12px var(--s4); margin: 0;
      border: 1px solid rgba(0,255,65,.2); background: rgba(0,0,0,.4);
      font-size: 13px; color: var(--cyan); word-break: break-all;
    }}
    .transfer__actions {{ display: grid; grid-template-columns: 1fr auto auto; gap: var(--s3); }}
    .callout {{
      padding: 14px var(--s4); border-left: 2px solid var(--yellow); background: rgba(255,214,10,.06);
      font-size: 12.5px; line-height: 1.6; color: var(--yellow);
    }}
    .callout--red {{ border-left-color: var(--red); background: rgba(255,43,77,.07); color: var(--red); }}

    #paySteps {{ display: flex; flex-direction: column; gap: var(--s8); }}
    .contact {{ display: flex; flex-direction: column; gap: var(--s4); }}
    .contact__row {{ display: grid; grid-template-columns: 1fr auto; gap: var(--s3); }}
    .contact__or {{ font-size: 11px; letter-spacing: 1px; color: var(--green-faint); text-align: center; }}

    .sheet {{
      position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center;
      padding: var(--s5); background: rgba(2,4,2,.82); backdrop-filter: blur(3px);
    }}
    .sheet__box {{
      width: min(420px, 100%); max-height: 80vh; overflow-y: auto;
      display: flex; flex-direction: column; gap: var(--s4); padding: var(--s6);
      border: 1px solid var(--green); background: #060a06; box-shadow: 0 0 32px rgba(0,255,65,.18);
    }}
    .sheet__head {{
      display: flex; align-items: center; justify-content: space-between;
      font-size: 10.5px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--green-faint);
    }}
    .sheet__x {{
      width: 28px; height: 28px; border: 1px solid var(--line); background: transparent;
      color: var(--green-dim); font: inherit; cursor: pointer;
    }}
    .sheet__x:hover {{ border-color: var(--line-strong); color: var(--green); }}
    .sheet__list {{ display: flex; flex-direction: column; gap: var(--s4); }}
    .sheet__group {{ display: flex; flex-direction: column; gap: var(--s2); }}
    .sheet__grouplabel {{ font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--green-faint); }}
    .sheet__qr {{ width: 100%; margin-top: var(--s2); }}
    .wallet {{
      display: flex; align-items: center; gap: var(--s3); min-height: var(--ctrl); padding: 0 var(--s4);
      border: 1px solid var(--line); background: var(--panel); color: var(--green-dim);
      font: inherit; font-size: 13.5px; text-align: left; cursor: pointer; text-decoration: none;
    }}
    .wallet:hover {{ border-color: var(--green); background: rgba(0,255,65,.06); color: var(--green); }}
    .wallet img {{ width: 22px; height: 22px; flex: none; }}

    .block {{ border: 1px solid var(--line); background: var(--panel); padding: var(--s6) 28px; display: flex; flex-direction: column; gap: 14px; }}
    .block-green {{ border-color: var(--green); background: rgba(0,255,65,.05); }}
    .block-red {{ border-color: rgba(255,43,77,.5); background: rgba(255,43,77,.05); }}
    .block-yellow {{ border-color: rgba(255,214,10,.5); background: rgba(255,214,10,.05); }}
    .mono-box {{
      overflow-wrap: anywhere; color: var(--cyan); border: 1px solid rgba(0,255,65,.2);
      padding: 12px var(--s4); background: rgba(0,0,0,.4); font-size: 13px; margin: 0;
    }}
    .hint {{ font-size: 12px; margin: 0; }}
    .qr-wrap {{ width: min(280px, 100%); padding: 12px; background: #fff; }}
    .qr-wrap img {{ display: block; width: 100%; height: auto; }}

    .guides {{ display: flex; flex-direction: column; gap: var(--s2); }}
    .guides details {{ border: 1px solid rgba(0,255,65,.14); background: var(--panel); }}
    .guides summary {{ padding: 14px 18px; cursor: pointer; font-size: 13px; }}
    .guides ol {{ margin: 0; padding: 0 18px 16px 40px; font-size: 13px; line-height: 1.9; color: rgba(0,255,65,.6); }}
    .howto li b {{ color: var(--green); font-weight: 400; }}
    code {{ color: var(--cyan); }}

    .field {{
      width: 100%; height: var(--ctrl); padding: 0 var(--s4);
      background: rgba(0,0,0,.4); border: 1px solid rgba(0,255,65,.2); color: var(--green);
      font: inherit; font-size: 13.5px;
    }}
    .field::placeholder {{ color: var(--green-faint); }}
    .field:focus {{ outline: 1px solid var(--line-strong); outline-offset: 2px; }}

    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); }}
    .orders {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    .orders th, .orders td {{ border: 1px solid var(--line); padding: 8px 10px; text-align: left; white-space: nowrap; }}
    .orders th {{ color: var(--green-faint); font-weight: 400; }}
    .orders .tx {{ max-width: 140px; overflow: hidden; text-overflow: ellipsis; }}

    .legal-text {{ font-size: 13px; line-height: 1.8; color: rgba(0,255,65,.6); }}
    .legal-text h2 {{ color: var(--green); font-size: 14px; margin: 22px 0 8px; font-weight: 400; }}
    .legal-text p {{ margin: 0 0 12px; }}
    .legal-text ul {{ margin: 0 0 12px; padding-left: 20px; }}
    .legal-text li {{ margin-bottom: 4px; }}

    .payment-badge {{ display: none; opacity: .85; transition: opacity .15s; }}
    .payment-badge:hover {{ opacity: 1; }}
    .payment-badge img {{ display: block; max-width: 100%; height: auto; border: 1px solid var(--line); }}

    @media (max-width: 720px) {{
      :root {{ --pad: 18px; }}
      .shell {{ border: 0; }}
      .chrome {{ height: 44px; padding: 0 var(--s4); }}
      .chrome__title {{ font-size: 10px; }}
      .main {{ gap: var(--s6); padding: var(--s6) var(--pad); }}
      .statusbar {{ height: 40px; padding: 0 var(--pad); font-size: 10px; }}

      h1 {{ font-size: 30px; line-height: 1.2; }}
      h1.small {{ font-size: 26px; }}
      .subhead {{ font-size: 12.5px; }}
      .cta {{ width: 100%; align-self: stretch; }}
      .syslog, .log {{ font-size: 11.5px; }}

      .tariff {{ grid-template-columns: 1fr auto; gap: var(--s2) var(--s3); padding: var(--s4); }}
      .tariff-price-block {{ grid-column: 2; grid-row: 1; }}
      .tariff-badge {{ grid-column: 2; grid-row: 2; width: 48px; height: 22px; font-size: 11px; }}
      .tariff-name {{ font-size: 13.5px; }}
      .tariff-info {{ grid-column: 1; grid-row: 1 / span 2; }}

      .steps {{ grid-template-columns: 1fr; gap: var(--s2); }}
      .step {{ flex-direction: row; align-items: center; gap: var(--s3); padding: 14px var(--s4); }}
      .step__n {{ min-width: 28px; }}
      .step__text {{ font-size: 12.5px; }}

      .order__head {{ flex-direction: column; align-items: flex-start; gap: var(--s4); }}
      .order__meta {{ grid-template-columns: auto 1fr; text-align: left; width: 100%; font-size: 11.5px; }}

      .coins--4 {{ grid-template-columns: repeat(2, 1fr); }}
      .coins {{ gap: var(--s2); }}
      .coin {{ gap: 9px; padding: 0 14px; font-size: 13px; }}
      .coin-group-dropdown {{ gap: var(--s2); }}
      .coin-group-label {{ min-width: 52px; font-size: 13px; }}

      .card-pay {{ grid-template-columns: 1fr; gap: var(--s3); padding: var(--s4); }}
      .card-pay .btn {{ justify-self: stretch; width: 100%; }}
      .card-brands {{ display: grid; grid-template-columns: repeat(3, 1fr); }}
      .card-brands span {{ padding: 0; font-size: 9.5px; }}

      .contact__row {{ grid-template-columns: 1fr; }}
      .contact__row .btn {{ width: 100%; }}
      .sheet {{ align-items: flex-end; padding: 0; }}
      .sheet__box {{ width: 100%; max-height: 88vh; }}

      .transfer {{ padding: var(--s5) 18px; gap: var(--s5); }}
      .transfer__amount {{ font-size: 28px; }}
      .field__value {{ font-size: 11.5px; line-height: 1.5; }}
      .transfer__actions {{ grid-template-columns: 1fr; gap: var(--s2); }}
      .callout {{ font-size: 12px; padding: 12px 14px; }}

      .block, .panel {{ padding: 18px; }}
      .actions {{ flex-direction: column; align-items: stretch; }}
      .actions .btn, .actions .cta {{ width: 100%; }}
      .guides ol {{ padding-left: 32px; }}
      .notes {{ font-size: 11.5px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .cursor {{ animation: none; }}
      * {{ transition: none !important; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="chrome">
      <div class="chrome__dots"><i></i><i></i><i></i></div>
      <span class="chrome__title">vpn-router — bash — 80×24</span>
    </header>
    <main class="main">{body}</main>
    <footer class="statusbar">STATUS: <b>CONNECTED</b> · UPTIME 99.98% · ENCRYPTION AES-256</footer>
  </div>
</body>
</html>"""
