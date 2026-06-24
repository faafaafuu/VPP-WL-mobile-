# Node Scaling Architecture

Стратегии масштабирования VPN-нод для subscription-link MVP.

---

## Текущая архитектура (MVP)

Ноды задаются через env vars (`VPN_NODE_1_*` … `VPN_NODE_10_*`) или загружаются из SQLite.
Сервер при старте заполняет БД нодами из env. Подписки генерируют VLESS-ссылки из всех **активных** нод, отсортированных по `priority`.

**Ограничения env-подхода:**
- Максимум 10 нод
- Требует перезапуска для изменений
- Нет web UI

---

## Admin API: горячее добавление нод (без рестарта)

### `POST /api/admin/nodes` — добавить/обновить ноду

```bash
curl -X POST http://SERVER/api/admin/nodes \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "node_nl_2",
    "tag": "vless-nl-2",
    "host": "5.6.7.8",
    "port": 443,
    "protocol": "vless",
    "region": "eu-west",
    "country_code": "NL",
    "provider": "hetzner",
    "priority": 15,
    "status": "active",
    "options": {
      "uuid": "YOUR-UUID-HERE",
      "server_name": "www.microsoft.com",
      "public_key": "YOUR_PUBLIC_KEY",
      "short_id": "YOUR_SHORT_ID",
      "flow": "xtls-rprx-vision",
      "fingerprint": "chrome",
      "label": "NL #2"
    }
  }'
```

### `DELETE /api/admin/nodes/{id}` — отключить ноду

```bash
curl -X DELETE http://SERVER/api/admin/nodes/node_nl_2 \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN"
```

Нода переходит в `status=disabled, health=disabled` — перестаёт отдаваться в подписках.

### `GET /api/admin/nodes` — список всех нод

```bash
curl http://SERVER/api/admin/nodes \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN"
```

### `PATCH /api/admin/nodes/{id}/health` — обновить health score

```bash
curl -X PATCH http://SERVER/api/admin/nodes/node_nl_2/health \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"health_score": 95, "status": "active", "latency_ms": 45}'
```

---

## Стратегии масштабирования

### 1. Вертикальное: больше нод на одном сервере

Один сервер с Xray может слушать несколько портов:

```json
"inbounds": [
  { "port": 443,  "protocol": "vless", "settings": {"clients": [{"id": "UUID_1"}]} },
  { "port": 8443, "protocol": "vless", "settings": {"clients": [{"id": "UUID_2"}]} },
  { "port": 2053, "protocol": "vless", "settings": {"clients": [{"id": "UUID_3"}]} }
]
```

Каждый inbound = отдельная нода в backend (разные `VPN_NODE_N_PORT`).

**Когда подходит:** до ~500 одновременных соединений на сервере. Дёшево — один VPS.

---

### 2. Горизонтальное: несколько серверов в разных гео

```
                  ┌─────────────────┐
  Пользователь ──► │  backend/API    │
                  │  (ноды в SQLite) │
                  └────────┬────────┘
                           │ subscription URL (список нод)
                  ┌────────▼────────┐
                  │  Клиент (Hiddify│
                  │  v2rayN и т.д.) │
                  └────────┬────────┘
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Node NL-1     Node DE-1    Node FI-1
         (Hetzner)    (Hetzner)   (Hetzner)
```

Backend отдаёт **все активные ноды** в одном subscription URL. Клиент автоматически переключается при падении ноды.

**Когда подходит:** geo-диверсификация, резервирование. 5–50 нод.

**Добавление новой ноды:**
1. Арендуй новый VPS
2. Установи Xray, сгенерируй ключи (`xray x25519`)
3. POST /api/admin/nodes с новыми данными
4. Клиенты получат новую ноду при следующем обновлении подписки

---

### 3. Geo-routing: разные ноды для разных регионов

Пока не реализовано, но архитектура позволяет:

```
GET /sub/{token}?region=eu  → только EU-ноды
GET /sub/{token}?region=us  → только US-ноды
GET /sub/{token}             → все ноды (текущее поведение)
```

Или автоматически по IP клиента при запросе подписки:

```python
def v2ray_subscription(token, client_ip=None):
    nodes = self.repository.list_nodes()
    if client_ip:
        preferred_region = geoip_lookup(client_ip)
        nodes = sort_by_region_proximity(nodes, preferred_region)
    return encoded_subscription(nodes[:5])  # топ-5 ближайших
```

**Что нужно реализовать:** MaxMind GeoIP DB (бесплатная) + фильтрация нод по country_code/region.

---

### 4. Автоматическое масштабирование (Long-term)

Для полностью автоматизированного управления нодами:

```
Event: "нагрузка на ноду > 80%"
  → Trigger: create new VPS (Hetzner API / Terraform)
  → Install: Ansible playbook (Xray + config)
  → Register: POST /api/admin/nodes
  → Done: новая нода в пуле через ~5 минут
```

**Инструменты:** Terraform (инфра), Ansible (Xray provisioning), GitHub Actions / cron (оркестрация).

Это уместно при 100+ активных пользователях.

---

## Priority и health score

Клиент получает ноды **отсортированные по priority** (меньше = выше). Ноды с `health_score < 40` или `success_rate < 0.75` исключаются из подписок.

**Рекомендации:**
- `priority=10` — основная быстрая нода
- `priority=20-30` — запасные ноды
- `priority=50` — резерв/тест
- `status=draining` — нода выводится из ротации (старые подключения доживают, новые не приходят)
- `status=disabled` — полностью отключена

---

## Сколько нод нужно

| Пользователей | Рекомендация |
|---------------|--------------|
| 1–50          | 1–2 ноды, 1 сервер |
| 50–500        | 3–5 нод, 2–3 сервера в разных гео |
| 500–5000      | 5–20 нод, geo-routing, health checker |
| 5000+         | Load balancer + auto-scaling |

**Правило большого пальца:** 1 Xray нода на ~200–500 одновременных подключений (зависит от канала сервера).

---

## Как добавить новую ноду за 10 минут

```bash
# 1. На новом VPS: установить xray и сгенерировать ключи
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
xray x25519  # запиши Public key
openssl rand -hex 8  # это Short ID
python3 -c "import uuid; print(uuid.uuid4())"  # UUID

# 2. Написать /usr/local/etc/xray/config.json (см. server-setup-vless-reality.md)
# 3. systemctl start xray

# 4. Зарегистрировать ноду в backend
curl -X POST https://YOUR_BACKEND/api/admin/nodes \
  -H "X-Admin-Token: $VPN_ROUTER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id":"node_nl_3","host":"NEW_IP","port":443,"protocol":"vless",
       "region":"eu-west","country_code":"NL","priority":25,
       "options":{"uuid":"NEW_UUID","server_name":"www.microsoft.com",
                  "public_key":"NEW_PUBKEY","short_id":"NEW_SID",
                  "label":"NL #3"}}'
```

Готово. Клиенты получат новую ноду при следующем обновлении подписки.
