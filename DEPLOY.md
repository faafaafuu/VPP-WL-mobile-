# Прод

Всё, что обслуживает продукт, живёт в одном compose-проекте `vpn-router`
в этом каталоге. Systemd больше ничего из этого не запускает.

```
docker compose ps          что поднято
docker compose logs -f api логи сайта
docker compose up -d       поднять / применить изменения
docker compose restart api перезапустить сайт после правок кода
```

Сборка образа нужна после любых изменений в `backend/`:

```
docker compose up -d --build api
```

## Сервисы

| сервис | что делает | наружу |
|---|---|---|
| `api` | сайт, бот, сверка платежей | нет, только через nginx |
| `nginx` | TLS-фронт: cleohop.ru, маскировка, XHTTP | 80, 443 |
| `hysteria2` | UDP-нода | 36712/udp |
| `xray-relay` | приёмник цепи с московской ноды | 11081 |
| `xray-xhttp` | транспорт за маскировкой | нет |

## База

`backend/data/vpn-router.db`, каталогом на хосте — не в именованном томе.
Так сделано намеренно: том однажды разошёлся с боевой базой на два месяца,
и `compose up` поднял бы приложение с чужими заказами.

База в режиме WAL. Копировать `.db` отдельно нельзя — часть заказов лежит
в `-wal` и потеряется. Только так:

```
sqlite3 backend/data/vpn-router.db ".backup '/root/backup.db'"
```

## Сертификаты

Выпускает и продлевает системный certbot в `/etc/letsencrypt`, оба
контейнера монтируют его только на чтение. Метод — `webroot` через
`/var/www/html`: плагин `--nginx` правил бы конфиг на хосте, которого у
контейнера нет.

После продления `/etc/letsencrypt/renewal-hooks/deploy/reload-stack.sh`
перезагружает nginx и перезапускает hysteria2 — иначе оба продолжали бы
отдавать старый сертификат.

## Откат на systemd

Хостовые конфиги nginx остались нетронутыми в `/etc/nginx/sites-available/`:

```
docker compose down
systemctl enable --now nginx vpn-router
```
