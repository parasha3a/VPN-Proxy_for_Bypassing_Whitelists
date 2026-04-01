<div align="center">
  <h1>VPN / Proxy Deploy Toolkit</h1>
  <p><strong>Self-hosted stack for bypassing DPI, whitelist blocks and regional filtering.</strong></p>
  <p>Русскоязычная документация, VPS installer, web admin, Telegram bot, квоты, подписки и hardened-by-default серверный сетап.</p>

  <p>
    <img src="https://img.shields.io/badge/Python-CLI-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python CLI" />
    <img src="https://img.shields.io/badge/Bash-Installer-121011?style=for-the-badge&logo=gnubash&logoColor=white" alt="Bash installer" />
    <img src="https://img.shields.io/badge/Linux-Ubuntu%2022.04%2B-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" />
    <img src="https://img.shields.io/badge/Web-Admin_Panel-0F172A?style=for-the-badge&logo=html5&logoColor=white" alt="Web admin" />
  </p>
  <p>
    <img src="https://img.shields.io/badge/Xray-core-REALITY%20%2B%20WS%20%2B%20gRPC-111827?style=for-the-badge" alt="Xray" />
    <img src="https://img.shields.io/badge/Hysteria2-QUIC%20fallback-0EA5E9?style=for-the-badge" alt="Hysteria2" />
    <img src="https://img.shields.io/badge/WireGuard-AmneziaWG-88171A?style=for-the-badge&logo=wireguard&logoColor=white" alt="WireGuard" />
    <img src="https://img.shields.io/badge/Telegram-Bot%20%2B%20MTProto-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" />
  </p>
</div>

Самостоятельный набор для развёртывания VPN и прокси на своём VPS: Xray, Hysteria2, AmneziaWG, WireGuard, HTTP/SOCKS5, MTProto, web-админка, CLI, Telegram bot, квоты и подписки без внешней панели управления и без отдельной базы данных.

`vpn-deploy` рассчитан на сценарий "один сервер, один репозиторий, один control plane". Установщик поднимает сервисы, настраивает firewall и SSH hardening, генерирует клиентские конфиги, публикует subscription endpoint и оставляет админку только на `127.0.0.1`.

## Содержание

- [Что это такое](#что-это-такое)
- [Что устанавливается](#что-устанавливается)
- [Требования к VPS](#требования-к-vps)
- [Быстрый старт](#быстрый-старт)
- [Подробная установка на VPS](#подробная-установка-на-vps)
- [Что спросит установщик](#что-спросит-установщик)
- [Что происходит после установки](#что-происходит-после-установки)
- [Проверка после установки](#проверка-после-установки)
- [Как открыть web-админку](#как-открыть-web-админку)
- [Как создать первого пользователя](#как-создать-первого-пользователя)
- [Что получает каждый пользователь](#что-получает-каждый-пользователь)
- [Поддерживаемые клиенты](#поддерживаемые-клиенты)
- [Матрица протоколов и портов](#матрица-протоколов-и-портов)
- [Основные команды CLI](#основные-команды-cli)
- [Telegram bot](#telegram-bot)
- [Безопасность по умолчанию](#безопасность-по-умолчанию)
- [Структура проекта](#структура-проекта)
- [Где лежат данные и секреты](#где-лежат-данные-и-секреты)
- [Обновление и удаление](#обновление-и-удаление)
- [Устранение проблем](#устранение-проблем)
- [Полезные ссылки](#полезные-ссылки)
- [Кратко на английском](#english-summary)
- [Чек-лист проверки](#чек-лист-проверки)

## Что это такое

`vpn-deploy` - это self-hosted стек для обхода DPI, whitelist-блокировок и региональной фильтрации на одном VPS.

Что он делает:

- ставит серверный стек одной командой через `install.sh`;
- создаёт единый CLI `vpn`;
- генерирует конфиги и subscription links для пользователей;
- считает трафик и умеет ставить квоты;
- даёт две админские поверхности: terminal panel и локальную web-админку;
- при желании поднимает Telegram bot для admin-only операций.

У проекта нет внешней панели, SaaS-слоя, биллинга и отдельной БД. Состояние хранится локально в JSON и `.env`.

## Что устанавливается

По умолчанию установщик разворачивает:

- Xray-core: VLESS Reality TCP, XHTTP, WS, gRPC и VMess WS;
- Hysteria2;
- AmneziaWG;
- HTTP и SOCKS5 proxy через `3proxy`;
- MTProto proxy через `mtg`;
- subscription server и локальную admin UI;
- terminal CLI и TTY panel;
- базовое hardening-окружение: `ufw`, `fail2ban`, более строгие права, systemd sandboxing.

Опционально можно включить:

- обычный WireGuard;
- selective Cloudflare WARP egress для проблемных доменов;
- Telegram bot.

## Требования к VPS

Минимально необходимое:

- Ubuntu 22.04+ или Debian 12+;
- root-доступ или пользователь с `sudo` и правом выполнять установку от root;
- публичный IP-адрес;
- рабочий SSH-доступ на сервер;
- чистый или хотя бы не слишком "ручной" VPS, где ваши старые настройки `ufw`, `iptables`, `xray`, `wireguard` и `sshd` не конфликтуют с новым стеком.

Перед установкой стоит понимать:

- web-админка по умолчанию не публикуется наружу, она слушает `127.0.0.1:8081`;
- subscription endpoint публичный и слушает `0.0.0.0:8000` или другой порт, который вы выберете;
- установщик меняет firewall и SSH hardening;
- после установки появится пользователь `admin` с готовым набором конфигов.

## Быстрый старт

Если нужен только краткий сценарий:

```bash
apt-get update
apt-get install -y git
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists/vpn-deploy
sudo ./install.sh
```

После установки:

```bash
vpn status
vpn user list
vpn user add alice
vpn user info alice
vpn user export alice --zip
```

## Подробная установка на VPS

Ниже нормальный пошаговый runbook для нового VPS.

### 1. Подготовьте сервер

Создайте VPS у любого провайдера и получите:

- IP-адрес сервера;
- root-пароль или SSH-ключ;
- доступ по SSH.

Сразу определитесь, что вы будете раздавать клиентам:

- домен, если он у вас уже есть;
- либо просто внешний IP сервера.

Если домена нет, стек работает и по IP.

### 2. Подключитесь к серверу

```bash
ssh root@YOUR_SERVER_IP
```

Если root у провайдера отключён и у вас sudo-пользователь:

```bash
ssh youruser@YOUR_SERVER_IP
sudo -i
```

### 3. Обновите систему и поставьте Git

```bash
apt-get update
apt-get upgrade -y
apt-get install -y git
```

Дополнительно полезно проверить время и hostname:

```bash
timedatectl
hostnamectl
```

### 4. Клонируйте репозиторий

```bash
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists/vpn-deploy
```

### 5. Запустите установщик

```bash
sudo ./install.sh
```

Во время установки скрипт:

- определит публичный IP;
- найдёт основной сетевой интерфейс;
- спросит имя сервера, хост/IP для раздачи и порты;
- сгенерирует `VPN_PANEL_TOKEN`, если его ещё нет;
- поставит зависимости через `apt`;
- развернёт и включит сервисы;
- создаст симлинк `/usr/local/bin/vpn`;
- создаст первого пользователя `admin`;
- применит security hardening.

Если установка проходит на полностью новом VPS, отдельные зависимости руками обычно ставить не нужно. Скрипт делает это сам.

## Что спросит установщик

Вот основные вопросы, которые задаёт `install.sh`, и как на них отвечать.

### `Server name`

Это человекочитаемое имя сервера. Оно попадает в названия конфигов и подписок.

Пример:

```text
MyVPN
```

### `Share host/IP`

Это адрес, который будет встроен в клиентские конфиги.

Что ставить:

- домен, если он уже настроен на ваш VPS;
- IP-адрес, если домена нет.

Примеры:

```text
vpn.example.com
203.0.113.10
```

### `Network interface`

Обычно установщик сам определяет правильный интерфейс, например `eth0` или `ens3`. Меняйте только если точно понимаете, что у вас другой основной NIC.

### Порты

Установщик спросит порты для:

- VLESS Reality;
- VLESS XHTTP;
- VLESS WS;
- VLESS gRPC;
- VMess WS;
- Hysteria2;
- HTTP proxy;
- SOCKS5 proxy;
- subscription server;
- MTProto;
- WireGuard.

Если нет причины менять, оставляйте defaults. Они уже согласованы между шаблонами, firewall и сервисами.

### `Install plain WireGuard too?`

Если нужен классический WireGuard, отвечайте `y`. Если достаточно AmneziaWG и остальных transport-вариантов, оставляйте `n`.

### `Enable selective Cloudflare WARP egress for problematic domains?`

Это опциональный режим для отдельных доменов, которые могут хуже открываться через обычные маршруты. Если вы не знаете, зачем он нужен, оставляйте `n`.

### `Install Telegram bot?`

Если хотите управлять сервером через Telegram, отвечайте `y`. Тогда установщик отдельно попросит:

- `Telegram bot token`
- `Telegram ADMIN_CHAT_ID`

Если бот пока не нужен, отвечайте `n`. Позже эти значения можно добавить в `data/server.env`.

## Что происходит после установки

После успешного завершения вы получаете:

- рабочую команду `vpn` в `/usr/local/bin/vpn`;
- публичные подписки по адресу `http://SERVER:SUB_PORT/sub/<name>`;
- локальную web-админку на `http://127.0.0.1:8081/`;
- `VPN_PANEL_TOKEN` в `data/server.env`;
- пользователя `admin` в каталоге `users/admin`;
- активные systemd units для поднятых сервисов.

Установщик в конце печатает:

- статус сервисов;
- admin subscription;
- путь к проекту;
- путь к admin bundle;
- команду для SSH tunnel в админку.

## Проверка после установки

Сразу после первого деплоя я бы проверял так.

### Проверка статуса

```bash
vpn status
```

### Проверка списка пользователей

```bash
vpn user list
```

Там должен быть хотя бы `admin`.

### Проверка subscription endpoint

Замените `SERVER` и `PORT` на ваши значения:

```bash
curl http://SERVER:PORT/sub/admin
```

Ожидаемый результат: base64-строка с подпиской.

Для сырого текста:

```bash
curl http://SERVER:PORT/sub/admin/raw
```

### Проверка сервисов через systemd

```bash
systemctl status xray
systemctl status hysteria
systemctl status vpn-sub
systemctl status 3proxy
systemctl status mtg
```

Если вы включали WireGuard, AmneziaWG или bot, проверьте и их.

## Как открыть web-админку

Админка по умолчанию локальная, то есть на самом VPS она слушает:

```text
http://127.0.0.1:8081/
```

Снаружи её нужно открывать через SSH tunnel.

### 1. На своём компьютере откройте tunnel

```bash
ssh -L 8081:127.0.0.1:8081 root@YOUR_SERVER_IP
```

### 2. Откройте браузер

```text
http://127.0.0.1:8081/
```

### 3. Возьмите токен из `data/server.env`

На VPS:

```bash
grep '^VPN_PANEL_TOKEN=' data/server.env
```

Скопируйте значение и вставьте его в форму входа.

В web-админке можно:

- создавать и удалять пользователей;
- смотреть generated files;
- копировать subscription URLs;
- скачивать ZIP bundle;
- ставить квоты или отключать их;
- suspend/resume пользователей;
- сбрасывать traffic usage;
- смотреть CPU, RAM, disk и network load.

## Как создать первого пользователя

После установки уже есть `admin`, но обычно создают отдельного реального пользователя.

### Создание

```bash
vpn user add alice
```

### Просмотр информации

```bash
vpn user info alice
```

### Экспорт ZIP-архива

```bash
vpn user export alice --zip
```

### Просмотр usage

```bash
vpn user usage alice
```

### Ограничение по трафику

```bash
vpn user limit alice --quota-gb 50
```

### Снятие ограничения

```bash
vpn user limit alice --disable
```

### Временная блокировка

```bash
vpn user suspend alice
```

### Возврат доступа

```bash
vpn user resume alice
```

Конфиги и файлы пользователя лежат в:

```text
users/alice/
```

## Что получает каждый пользователь

| Файл | Назначение |
|---|---|
| Subscription URL | Одна ссылка для импорта всех поддерживаемых подключений |
| `uris.txt` | VLESS Reality TCP, XHTTP, WS, gRPC, VMess WS, Hysteria2 |
| `xray_client.json` | Конфиг для клиентов на базе Xray |
| `singbox_client.json` | Конфиг для sing-box-совместимых клиентов |
| `hy2_client.yaml` | Отдельный конфиг Hysteria2 |
| `wg.conf` | Конфиг WireGuard |
| `awg.conf` | Конфиг AmneziaWG |
| `proxy.txt` | HTTP и SOCKS5 credentials |
| `mtproto.txt` | Ссылки и параметры для Telegram proxy |
| `qr_*.png` | QR-коды для мобильного импорта |
| `README.txt` | Человекочитаемая памятка внутри user bundle |

## Поддерживаемые клиенты

Ниже не "жёсткий whitelist", а проверенный набор клиентов, под которые проект уже генерирует данные в удобном виде.

| Клиент | Платформа | Subscription | URI | Импорт файла | Комментарий |
|---|---|:---:|:---:|:---:|---|
| v2rayN | Windows / Linux / macOS | ✅ | ✅ | Xray | Основной desktop-клиент |
| Throne | Windows / Linux / macOS | ✅ | ✅ | Xray / sing-box | Современный successor Nekoray |
| Karing | Windows / Linux / macOS / iOS | ✅ | ✅ | sing-box | Сильный мультиплатформенный вариант |
| AmneziaVPN | Windows / Linux / macOS / iOS / Android | - | ✅ | Xray / WG / AWG | Удобен для file-based import |
| Happ | macOS / iOS / tvOS | ✅ | ✅ | Xray | Поддерживает ссылки и JSON |
| Streisand | iOS | ✅ | ✅ | sing-box | Хороший основной клиент для iPhone |
| Shadowrocket | iOS | ✅ | ✅ | - | Удобен для прямого URI import |
| V2Box | iOS / Android | ✅ | ✅ | - | Простой consumer-клиент |
| v2RayTun | iOS / Android | ✅ | ✅ | sing-box | Полезен для TUN-сценариев |
| v2rayNG | Android | ✅ | ✅ | - | Основной Android-вариант |
| NekoBox | Android | ✅ | ✅ | sing-box | Хорош для продвинутых Android-настроек |

## Матрица протоколов и портов

Порты по умолчанию:

| Протокол | Порт | Роль |
|---|---|---|
| VLESS + XTLS-Reality TCP | `443/tcp` | Основной transport |
| VLESS + Reality XHTTP | `8443/tcp` | Fallback под HTTP-поведение |
| VLESS + WS | `8444/tcp` | WebSocket fallback |
| VLESS + gRPC | `8445/tcp` | gRPC fallback |
| VMess + WS | `8446/tcp` | Legacy compatibility |
| Hysteria2 | `443/udp` | QUIC/UDP fallback |
| HTTP proxy | `8080/tcp` | Браузеры и `curl` |
| SOCKS5 proxy | `1080/tcp` | Браузеры и `curl` |
| MTProto | `8447/tcp` | Telegram native proxy |
| Subscription server | `8000/tcp` | Подписки и raw export |
| WireGuard / AmneziaWG | `51820/udp` | VPN fallback |
| Admin UI | `8081/tcp` | Только локально на `127.0.0.1` |

Если вы меняете порты во время установки, эти значения будут записаны в `data/server.env` и использованы в шаблонах.

## Основные команды CLI

```bash
vpn install
vpn panel
vpn status
vpn logs
vpn update
vpn uninstall [--yes]

vpn user add <name>
vpn user del <name>
vpn user list [--json]
vpn user config <name>
vpn user info <name> [--no-qr]
vpn user export <name> [--zip] [--json]
vpn user usage [name] [--json]
vpn user limit <name> (--quota-gb N | --quota-bytes N | --disable) [--json]
vpn user suspend <name> [--json]
vpn user resume <name> [--json]
vpn user reset-usage <name> [--json]

vpn sub [--json]
vpn completion [bash|zsh]
```

Python entrypoint тоже доступен напрямую:

```bash
python3 scripts/vpn_manager.py user list --json
python3 scripts/vpn_manager.py status --json
python3 scripts/vpn_manager.py panel
```

## Telegram bot

Bot ставится опционально и работает как `vpn-bot.service`.

Он отвечает только `ADMIN_CHAT_ID`.

Основные команды:

| Команда | Что делает |
|---|---|
| `/start` | Показывает меню |
| `/add <name>` | Создаёт пользователя и отправляет bundle |
| `/del <name>` | Удаляет пользователя |
| `/list` | Показывает список пользователей |
| `/info <name>` | Повторно отправляет конфиги |
| `/status` | Показывает статус сервисов |
| `/logs` | Присылает свежие логи |

Если бот уже установлен и нужно поменять токен или chat ID:

```bash
grep -E '^(BOT_TOKEN|ADMIN_CHAT_ID)=' data/server.env
systemctl restart vpn-bot
```

## Безопасность по умолчанию

Что проект делает "из коробки":

- не публикует admin UI наружу;
- включает `ufw` с политикой `deny incoming`;
- включает `fail2ban` для SSH;
- ужесточает SSH-конфигурацию;
- запускает сервисы с более жёсткими systemd sandbox settings;
- кладёт runtime-файлы и user bundles с более строгими правами;
- оставляет Xray API на `127.0.0.1:10085`.

Что важно не сломать вручную:

- не пробрасывайте `8081/tcp` в интернет без отдельной защиты;
- не коммитьте реальные `data/server.env` и `data/users.json`;
- не раздавайте `VPN_PANEL_TOKEN`;
- не выключайте firewall без понимания, какие порты реально нужны вашим клиентам.

## Структура проекта

```text
vpn-deploy/
├── install.sh                # Основной установщик
├── vpn.sh                    # Thin wrapper -> python3 scripts/vpn_manager.py
├── bot.py                    # Telegram bot
├── sub_server.py             # Subscription server + local-only admin API/UI
├── scripts/
│   ├── vpn_manager.py        # Основной CLI / TTY panel / JSON control plane
│   ├── install_xray.sh
│   ├── install_hysteria.sh
│   ├── install_wg.sh
│   ├── install_awg.sh
│   ├── install_proxy.sh
│   ├── install_mtproto.sh
│   ├── install_sub.sh
│   ├── install_bot.sh
│   ├── install_warp.sh
│   ├── install_network_tuning.sh
│   ├── install_security_hardening.sh
│   └── utils.sh
├── templates/                # JSON/YAML/URI templates
├── web/                      # Frontend админки
├── data/                     # Локальные runtime-данные, env, generated files
├── users/                    # Персональные bundles и export-архивы
└── tests/                    # Python tests
```

## Где лежат данные и секреты

Главные файлы:

- `data/server.env` - все runtime settings и секреты;
- `data/server.env.example` - шаблон переменных;
- `data/users.json` - база пользователей;
- `data/usage_state.json` - состояние usage и квот;
- `data/generated/` - общие сгенерированные файлы;
- `users/<name>/` - персональные bundles.

Никогда не коммитьте:

- реальные `data/server.env`;
- реальные `data/users.json`;
- `data/usage_state.json`;
- приватные ключи, боевые токены, домены и IP, которые не должны светиться публично.

Если секреты уже попали в git:

```bash
git rm --cached data/server.env data/users.json
```

## Обновление и удаление

### Обновление

```bash
cd /path/to/vpn-deploy
git pull
vpn update
vpn status
```

Если вы меняли шаблоны или installer-скрипты вручную, сначала посмотрите diff и только потом обновляйтесь.

### Удаление

```bash
vpn uninstall --yes
```

Это сценарий полной очистки. Перед ним стоит сохранить:

- `data/server.env`;
- `data/users.json`;
- содержимое `users/`, если нужно восстановление клиентов;
- список нужных портов и доменов.

## Устранение проблем

### Админка не открывается

Проверьте:

```bash
systemctl status vpn-sub
grep '^VPN_PANEL_TOKEN=' data/server.env
ssh -L 8081:127.0.0.1:8081 root@YOUR_SERVER_IP
```

### Подписка не отдаётся

Проверьте:

```bash
vpn sub
curl http://127.0.0.1:8000/sub/admin
systemctl status vpn-sub
```

### Пользователь создан, но клиент не подключается

Проверяйте по цепочке:

```bash
vpn user info alice
vpn status
systemctl status xray
systemctl status hysteria
```

И отдельно смотрите:

- правильный ли `SERVER_HOST` в `data/server.env`;
- открыты ли нужные порты;
- не блокирует ли провайдер UDP или нестандартные TCP-порты;
- не импортирован ли старый конфиг вместо нового.

### Проблемы после ручной правки firewall или SSH

Если вы вручную меняли `ufw`, `iptables` или `sshd_config`, возможен конфликт с installer hardening. В этом случае сначала сравните ваши изменения с:

- `scripts/install_security_hardening.sh`
- `data/server.env`

## Полезные ссылки

### Клиенты

- v2rayN: https://github.com/2dust/v2rayN
- Throne: https://github.com/throneproj/Throne
- Karing: https://github.com/KaringX/karing
- AmneziaVPN: https://github.com/amnezia-vpn/amnezia-client
- Happ: https://github.com/Happ-proxy
- Streisand: https://apps.apple.com/us/app/streisand/id6450534064
- Shadowrocket: https://apps.apple.com/us/app/shadowrocket/id932747118
- v2rayNG: https://github.com/2dust/v2rayNG
- NekoBox: https://github.com/MatsuriDayo/NekoBoxForAndroid

### Серверные компоненты

- Xray-core: https://github.com/XTLS/Xray-core
- sing-box docs: https://sing-box.sagernet.org
- Hysteria2: https://github.com/apernet/hysteria
- mtg: https://github.com/9seconds/mtg
- WireGuard: https://www.wireguard.com

## English Summary

`vpn-deploy` is a self-hosted VPN/proxy stack for a single VPS. It installs Xray, Hysteria2, AmneziaWG, optional WireGuard, 3proxy, MTProto, a subscription server, a local-only web admin UI and an optional Telegram bot.

Quick install:

```bash
apt-get update && apt-get install -y git
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists/vpn-deploy
sudo ./install.sh
```

Main operational commands:

```bash
vpn status
vpn user add alice
vpn user info alice
vpn user export alice --zip
```

The main documentation is now Russian-first. For admin UI access, use an SSH tunnel to `127.0.0.1:8081` and authenticate with `VPN_PANEL_TOKEN` from `data/server.env`.

## Чек-лист проверки

- [ ] Свежий Ubuntu 22.04+ или Debian 12+ проходит `./install.sh` без ошибок
- [ ] После установки `vpn status` показывает ожидаемый набор сервисов
- [ ] `vpn user add alice` создаёт все нужные файлы в `users/alice/`
- [ ] `curl http://SERVER:8000/sub/alice` возвращает base64
- [ ] `curl http://SERVER:8000/sub/alice/raw` возвращает текстовую подписку
- [ ] Subscription импортируется в v2rayN
- [ ] Subscription импортируется в v2rayNG
- [ ] Subscription импортируется в Karing
- [ ] Subscription импортируется в Streisand
- [ ] Subscription импортируется в NekoBox
- [ ] VLESS Reality URI импортируется в Shadowrocket
- [ ] Hysteria2 URI импортируется в совместимые клиенты
- [ ] `xray_client.json` импортируется в Xray-compatible clients
- [ ] `singbox_client.json` импортируется в Karing и NekoBox
- [ ] `awg.conf` импортируется в AmneziaVPN
- [ ] HTTP proxy работает через `curl -x`
- [ ] SOCKS5 proxy работает через `curl --socks5`
- [ ] MTProto link открывается в Telegram
- [ ] `vpn user del alice` корректно отзывает доступ
- [ ] Web admin открывается через SSH tunnel и принимает `VPN_PANEL_TOKEN`
- [ ] Bot `/add bob` отправляет ожидаемые файлы и QR, если bot включён
