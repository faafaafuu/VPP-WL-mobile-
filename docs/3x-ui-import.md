# Импорт VLESS-конфигов из 3x-ui

Текущий этап: 3x-ui — источник реальных VLESS/Reality конфигов на одном сервере.
vpn-router backend читает эти конфиги и отдаёт пользователям через subscription URL.

```
3x-ui (источник конфигов)
      │  vless:// ссылки
      ▼
vpn-router backend  ──►  /sub/{token}        (base64-подписка)
                    ──►  /sub/{token}/raw    (список vless://)
                    ──►  /sub/{token}/qr     (QR)
                    ──►  /connect/{token}    (статус + список вариантов)
      ▲
      │ одна постоянная ссылка
   v2rayN / v2rayNG / Hiddify / Streisand
```

**Принцип:** ничего не захардкожено в клиенте. Тарифы, тексты, список серверов,
VLESS-ссылки, QR и статус — всё приходит с backend. Пользователь добавляет одну
ссылку `/sub/{token}` один раз; при обновлении подписки в приложении он получает
актуальный список конфигов.

---

## Безопасность

Реальные `vless://` содержат **UUID клиента и Reality-ключи** — это секреты.
**Не коммить их в git.** Импорт делается в рантайме в SQLite-БД (Docker volume
`backend-data`), файлы со ссылками держим вне репозитория.

---

## Способ 1. HTTP admin endpoint (рекомендуется, без рестарта)

Админ-токен — это `VPN_ROUTER_ADMIN_TOKEN` из `.env`, передаётся в заголовке
`X-Admin-Token`.

### Импортировать одну ссылку

```bash
curl -X POST http://127.0.0.1/admin/nodes/import-vless \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vless_url": "vless://UUID@84.247.166.53:2083?type=tcp&security=reality&pbk=...&fp=chrome&sni=www.cloudflare.com&sid=...#ignored",
    "label": "VPN Router 1 · Reality",
    "priority": 1,
    "enabled": true,
    "country_code": "DE"
  }'
```

Поле `label` важнее `#fragment` в самой ссылке — именно `label` увидит
пользователь в приложении. Пиши простыми словами: «Основной», «Резервный»,
«gRPC», «TCP» — без UUID/ключей.

### Посмотреть список нод

```bash
curl http://127.0.0.1/admin/nodes -H "X-Admin-Token: $ADMIN_TOKEN"
```

### Включить / выключить / переименовать ноду онлайн

```bash
# выключить
curl -X PATCH http://127.0.0.1/admin/nodes/{id} \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# поменять приоритет и метку
curl -X PATCH http://127.0.0.1/admin/nodes/{id} \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"priority": 1, "label": "Основной"}'
```

Изменения применяются сразу, без пересборки и без новой ссылки у пользователя.

---

## Способ 2. CLI (массовый импорт)

Запускается внутри контейнера backend (репозиторий — тот же SQLite volume):

```bash
# JSON-файл: [{"vless_url":"...","label":"...","priority":1,"enabled":true}, ...]
docker compose exec api python3 -m app.cli.import_vless --file /app/backend/data/nodes.json

# Простой текст: одна vless:// ссылка на строку (метка из #fragment)
docker compose exec api python3 -m app.cli.import_vless --file /app/backend/data/nodes.txt --text

# Посмотреть текущие ноды
docker compose exec api python3 -m app.cli.import_vless --list
```

---

## Где взять vless:// из 3x-ui

3x-ui установлен как **systemd-сервис** (`x-ui`), база — `/etc/x-ui/x-ui.db`
(SQLite), панель — порт из `/etc/x-ui/install-result.env`.

1. Зайди в панель 3x-ui → Inbounds.
2. У нужного inbound нажми на клиента → «QR / Ссылка» → скопируй `vless://...`.
3. Импортируй через endpoint или CLI выше с понятной меткой.

> Один сервер может отдавать несколько вариантов подключения (Reality на разных
> SNI/портах, TLS, gRPC). Это **не разные страны** — это разные способы
> подключения к одному серверу для обхода блокировок. Архитектура позволяет
> позже добавить другие серверы/страны без переписывания backend (поля
> `country_code`, `source`, `source_panel` у ноды).

---

## Что видит пользователь

- `/connect/{token}` — статус подписки, дата окончания, кнопки «Скопировать
  ссылку» / «Показать QR», **список доступных вариантов** (метки + тип) и
  короткая инструкция для v2rayN/v2rayNG/Hiddify.
- `/sub/{token}` — base64-подписка для приложения.
- `/sub/{token}/raw` — список `vless://` (для отладки).

Ссылка `/sub/{token}` **постоянная**. Менять список конфигов можно онлайн —
пользователю не нужна новая ссылка, только «Update subscription» в приложении.

---

## Будущий этап: автосинхронизация с 3x-ui по API

Сейчас импорт ручной (безопасно, не трогает 3x-ui). Позже можно добавить
синхронизацию через HTTP API 3x-ui (логин по сессии/токену → чтение inbounds →
автообновление нод). Поля `source=3x-ui` и `source_panel=local-3x-ui` уже
заложены в модель для этого.

---

## Routing / geo (текущий этап)

Обычная `/sub/{token}` отдаёт **только список серверов**. Маршрутизация
(что идёт напрямую, что через VPN) зависит от клиента, а не от подписки —
в формат V2Ray subscription routing не закладываем.

- **v2rayN:** включить routing/«Domain strategy» и правило direct для RU,
  если нужно (Settings → Routing).
- **Hiddify:** использовать встроенный routing profile, если доступен.

Полноценные geoip/geosite профили (sing-box, Clash) — отдельный этап. Будущие
endpoints зарезервированы и пока не реализованы, текущие не ломаются:
`/sub/{token}/singbox`, `/sub/{token}/clash`, `/routing/ru-direct`.
