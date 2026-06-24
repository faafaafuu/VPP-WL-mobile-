# Server Setup: VLESS Reality (5 nodes)

Руководство по поднятию до 5 VLESS Reality inbound-нод для subscription-link MVP.

---

## Требования

- VPS с публичным IP (Hetzner, DigitalOcean, Vultr, Contabo и т.п.)
- Ubuntu 22.04 / Debian 12
- Порт 443 открыт (TCP)
- `xray` установлен (см. ниже)

---

## 1. Установка Xray

```bash
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

Проверка:

```bash
xray version
```

---

## 2. Генерация ключей Reality

Для каждой ноды нужна отдельная пара ключей:

```bash
xray x25519
```

Пример вывода:

```
Private key: abc123...
Public key:  xyz789...
```

Запишите `Private key` (только для сервера, **никогда не кладите в git**) и `Public key` (пойдёт в env backend).

Для `Short ID`:

```bash
openssl rand -hex 8
```

---

## 3. Конфиг Xray (`/usr/local/etc/xray/config.json`)

Пример для **одной ноды** на порту 443.  
Reality маскируется под `www.microsoft.com` (SNI — публичный сайт с TLS 1.3).

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "PASTE_UUID_HERE",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.microsoft.com:443",
          "xver": 0,
          "serverNames": ["www.microsoft.com"],
          "privateKey": "PASTE_PRIVATE_KEY_HERE",
          "shortIds": ["PASTE_SHORT_ID_HERE"]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    { "protocol": "freedom", "tag": "direct" },
    { "protocol": "blackhole", "tag": "block" }
  ]
}
```

Для **5 нод на одном сервере** — использовать разные порты (443, 8443, 2053, 2087, 2096):

```json
"inbounds": [
  { "port": 443,  ... "clients": [{"id": "UUID_1"}], "realitySettings": {"privateKey": "KEY_1", "shortIds": ["SID_1"]} },
  { "port": 8443, ... "clients": [{"id": "UUID_2"}], "realitySettings": {"privateKey": "KEY_2", "shortIds": ["SID_2"]} },
  ...
]
```

Для **5 нод на разных серверах** — отдельный `config.json` на каждом сервере с одним inbound.

---

## 4. Запуск Xray

```bash
systemctl enable xray
systemctl start xray
systemctl status xray
```

Проверка соединения (с другого IP):

```bash
curl -I --connect-to www.microsoft.com:443:YOUR_SERVER_IP:443 https://www.microsoft.com/ 2>&1 | head -5
```

---

## 5. Генерация UUID для клиентов

Каждый клиент (пользователь) должен иметь **уникальный UUID**.  
Для MVP можно использовать один UUID (все пользователи подписки используют один ключ).

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

---

## 6. Настройка env backend

Добавьте в `.env` на сервере (или systemd service environment):

```bash
# Node 1 — NL, Hetzner
VPN_NODE_1_HOST=1.2.3.4
VPN_NODE_1_PORT=443
VPN_NODE_1_UUID=00000000-0000-4000-8000-000000000001
VPN_NODE_1_PUBLIC_KEY=xyz789_public_key_from_xray_x25519
VPN_NODE_1_SHORT_ID=deadbeef01020304
VPN_NODE_1_SNI=www.microsoft.com
VPN_NODE_1_FLOW=xtls-rprx-vision
VPN_NODE_1_FINGERPRINT=chrome
VPN_NODE_1_LABEL=Netherlands #1
VPN_NODE_1_REGION=eu-west
VPN_NODE_1_COUNTRY_CODE=NL
VPN_NODE_1_PRIORITY=10
VPN_NODE_1_ENABLED=true

# Node 2 — DE, Hetzner
VPN_NODE_2_HOST=5.6.7.8
VPN_NODE_2_PORT=443
VPN_NODE_2_UUID=00000000-0000-4000-8000-000000000002
VPN_NODE_2_PUBLIC_KEY=...
VPN_NODE_2_SHORT_ID=...
VPN_NODE_2_SNI=www.microsoft.com
VPN_NODE_2_LABEL=Germany #1
VPN_NODE_2_REGION=eu-central
VPN_NODE_2_COUNTRY_CODE=DE
VPN_NODE_2_PRIORITY=20
VPN_NODE_2_ENABLED=true

# ... повторить для NODE_3..5
```

**Важно:**
- Не кладите реальные `VPN_NODE_N_UUID`, `VPN_NODE_N_PUBLIC_KEY`, `VPN_NODE_N_SHORT_ID` в git.
- Используйте `VPN_NODE_N_ENABLED=false` для временного отключения ноды без удаления из конфига.
- Отключённые ноды не попадают в subscription URL.

---

## 7. Выбор SNI (server name)

Reality требует публичный домен с TLS 1.3 и HTTPS. Хорошие варианты:

| SNI | Пояснение |
|-----|-----------|
| `www.microsoft.com` | Стабильный, крупный, поддерживает TLS 1.3 |
| `www.apple.com` | То же |
| `addons.mozilla.org` | То же |
| `dl.google.com` | То же |

Не используйте домены РФ-провайдеров или ваши собственные домены как SNI — это деанонимизирует сервер.

---

## 8. Firewall

```bash
ufw allow 443/tcp
ufw allow 8443/tcp  # если используете второй порт
ufw enable
```

---

## Split tunneling: честное объяснение ограничений

### Что можно гарантировать

VLESS subscription URL передаёт клиенту только **список proxy-серверов** (vless:// ссылки).  
Клиент сам решает, какой трафик направить через VPN, а какой — напрямую.

### Что нельзя сделать через обычный subscription URL

**Нельзя** передать routing-правила («РУ-сайты напрямую, остальное через VPN») через стандартный V2Ray subscription format (`/sub/{token}` base64).

Это ограничение **формата**, а не нашего backend. Стандартный subscription — это просто список ссылок, не конфиг роутинга.

### Что могут делать разные клиенты

| Клиент | Split tunneling |
|--------|----------------|
| **Hiddify** (Android/iOS/macOS) | Поддерживает встроенные правила геороутинга. Пользователь включает «bypass Iran/Russia» в настройках. |
| **v2rayNG** (Android) | Есть правила роутинга, настраиваются вручную. |
| **v2rayN** (Windows) | Есть встроенный routing с geo-файлами. Пользователь включает «bypass mainland China/Russia» в настройках. |
| **Streisand** (iOS) | Базовый клиент, ограниченный роутинг. |
| **Shadowrocket** (iOS) | Поддерживает правила роутинга через config URL. |

### Инструкция для пользователей (short-term)

Рекомендуйте пользователям:
1. Установить **Hiddify** (Android/iOS/macOS) — лучшая поддержка геороутинга из коробки.
2. В настройках включить **«Bypass LAN & domestic»** или **«Bypass Iran/Russia»** (зависит от версии клиента).
3. В v2rayN (Windows): Settings → Routing → выбрать «Bypass mainland China» или добавить custom rules для `geoip:ru`.

### Почему нельзя сделать это на уровне сервера

Xray/sing-box server-side routing не помогает: сервер видит уже зашифрованный трафик от клиента. «РУ сайты напрямую» — значит трафик вообще не доходит до сервера. Это должен решать клиент на устройстве пользователя.

### Medium-term (отдельные profile endpoints)

Если потребуется полноценный routing config (не просто список нод), можно добавить отдельные endpoints:
- `GET /profile/hiddify/{token}` — Hiddify remote profile (JSON)
- `GET /profile/singbox/{token}` — sing-box config с routing rules

Это требует отдельной задачи и расширенного формата. **Не реализуется в рамках текущего MVP** без отдельного решения.

---

## Проверка работы после настройки

1. Запустите backend с реальными `VPN_NODE_*` env vars.
2. Откройте `PUBLIC_BASE_URL/` — выберите тариф, пройдите checkout.
3. Откройте `/connect/{token}` — скопируйте subscription URL.
4. В Hiddify: Add → Subscription URL → вставьте URL → Update.
5. Подключитесь — проверьте `ifconfig.me` или `2ip.ru`.
