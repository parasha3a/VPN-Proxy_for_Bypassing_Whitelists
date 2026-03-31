<div align="center">
  <h1>🛰️ VPN / Proxy Deploy Toolkit</h1>
  <p><strong>Self-hosted stack for bypassing DPI, whitelist blocks and regional filtering.</strong></p>
  <p>Python control plane, Bash installer, web admin, Telegram bot, quotas, load monitoring and hardened-by-default server setup.</p>

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

<p align="center">
  <a href="#english">English</a> ·
  <a href="#russian">Русский</a> ·
  <a href="#project-structure">Structure</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#web-admin">Web Admin</a> ·
  <a href="#security-defaults">Security</a>
</p>

---

<a id="english"></a>

## English

### What This Repository Is

`vpn-deploy` is a lightweight self-hosted VPN/proxy toolkit with no external control plane, no database and no billing layer. It installs the server stack, manages users, renders client configs, exposes a web admin UI, tracks traffic usage, applies quotas and keeps the public attack surface tighter than a typical hobby VPN setup.

### Why It Exists

- One server, one repo, one control plane.
- Several transport options instead of betting everything on one protocol.
- Fast user onboarding with subscription links, JSON configs, QR codes and ZIP bundles.
- Admin flows through both CLI and browser.
- Security defaults are opinionated enough for real public exposure.

### At a Glance

| Area | What you get |
|---|---|
| Provisioning | `install.sh` installs Xray, Hysteria2, WireGuard, AmneziaWG, 3proxy, MTProto, sub server, bot and hardening |
| Control plane | `vpn` CLI backed by `scripts/vpn_manager.py` |
| Web | Built-in admin panel with user actions, quota control and server load view |
| Access methods | VLESS Reality TCP, XHTTP, WS, gRPC, VMess WS, Hysteria2, WireGuard, AmneziaWG, HTTP/SOCKS5, MTProto |
| Automation | JSON output for status, user info, exports, sub info, logs and quotas |
| Security | Local-only admin UI, UFW, fail2ban, stricter permissions, systemd sandboxing |
| Bypass extras | Optional selective WARP egress and emergency rescue feeds |

### Technology Stack

| Layer | Tech |
|---|---|
| Control plane | Python 3, `scripts/vpn_manager.py`, JSON storage |
| Installer | Bash, systemd units, dedicated install scripts |
| Proxy/VPN core | Xray-core, Hysteria2, WireGuard, AmneziaWG, 3proxy, mtg |
| Interfaces | TTY panel, web admin UI, Telegram bot |
| Templates | JSON, YAML, URI templates, QR and bundle generation |
| Security | OpenSSH hardening, UFW, fail2ban, local bind admin mode |

### Key Features

- `vpn` as a single entrypoint for install, status, logs, users, quotas and exports
- Interactive TTY panel for terminal-first operations
- Built-in web admin for user lifecycle, config download, proxy access and quota changes
- Per-user traffic accounting and traffic limits
- Server load metrics in CLI and web UI
- Legacy command compatibility for older operational scripts
- Subscription endpoint for one-link imports into popular clients
- Telegram bot for admin-only operational tasks

<a id="project-structure"></a>

### Project Structure

```text
vpn-deploy/
├── install.sh                # Main installer
├── vpn.sh                    # Thin wrapper -> python3 scripts/vpn_manager.py
├── bot.py                    # Telegram admin bot
├── sub_server.py             # Subscription server + local-only admin API/UI
├── scripts/
│   ├── vpn_manager.py        # Main CLI / TTY panel / JSON control plane
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
├── templates/               # Client/server templates and URI templates
├── web/                     # Admin frontend
├── data/                    # Local runtime data, generated configs, env files
├── users/                   # Per-user bundles and exports
└── tests/                   # Python tests
```

### Quick Start

```bash
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists
sudo ./install.sh
```

After install:

```bash
vpn user add alice
vpn user info alice
vpn user export alice --zip
vpn status
```

### What Gets Generated Per User

| File | Purpose |
|---|---|
| Subscription URL | `http://SERVER:8000/sub/<name>` imports all supported links |
| `uris.txt` | VLESS Reality TCP, XHTTP, WS, gRPC, VMess WS, Hysteria2 |
| `xray_client.json` | Xray outbound config for Xray-compatible clients |
| `singbox_client.json` | sing-box config for Karing, NekoBox, Streisand, v2RayTun |
| `hy2_client.yaml` | standalone Hysteria2 client config |
| `wg.conf` | WireGuard config |
| `awg.conf` | AmneziaWG config |
| `proxy.txt` | HTTP and SOCKS5 credentials |
| `mtproto.txt` | Telegram proxy links |
| `qr_*.png` | QR codes for mobile import |
| `README.txt` | Human-readable user bundle instructions |

### Protocol Matrix

| Protocol | Port | Role |
|---|---|---|
| VLESS + XTLS-Reality TCP | `443/tcp` | Primary transport |
| VLESS + Reality XHTTP | `8443/tcp` | HTTP-shaped fallback |
| VLESS + WS | `8444/tcp` | WebSocket fallback |
| VLESS + gRPC | `8445/tcp` | gRPC fallback |
| VMess + WS | `8446/tcp` | Legacy compatibility |
| Hysteria2 | `443/udp` | QUIC/UDP fallback |
| AmneziaWG | `51820/udp` | Obfuscated WireGuard |
| WireGuard | `51820/udp` | Plain WireGuard fallback |
| HTTP proxy | `8080/tcp` | Browser and curl |
| SOCKS5 proxy | `1080/tcp` | Browser and curl |
| MTProto | `8447/tcp` | Telegram native proxy |

### Supported Clients

| Client | Platform | Subscription | URI | File Import | Notes |
|---|---|:---:|:---:|:---:|---|
| v2rayN | Win/Linux/macOS | ✅ | ✅ | Xray | Primary desktop |
| Throne | Win/Linux/macOS | ✅ | ✅ | Xray/sing-box | Nekoray successor |
| Karing | Win/Linux/macOS/iOS | ✅ | ✅ | sing-box | Strong multi-platform option |
| AmneziaVPN | Win/Linux/macOS/iOS/Android | — | ✅ | Xray/WG/AWG | File-based import |
| Happ | macOS/iOS/tvOS | ✅ | ✅ | Xray | Supports links and JSON |
| Streisand | iOS | ✅ | ✅ | sing-box | Primary iOS option |
| Shadowrocket | iOS | ✅ | ✅ | — | Useful for direct URI import |
| V2Box | iOS/Android | ✅ | ✅ | — | Simple consumer client |
| v2RayTun | iOS/Android | ✅ | ✅ | sing-box | TUN-friendly import |
| v2rayNG | Android | ✅ | ✅ | — | Primary Android option |
| NekoBox | Android | ✅ | ✅ | sing-box | Good advanced Android client |

<a id="cli"></a>

### CLI

```bash
vpn install                     # Interactive setup wizard
vpn user add <name>             # Create user and generate all configs
vpn user del <name>             # Remove user from all services
vpn user list [--json]          # Table or JSON output
vpn user config <name>          # Paths to generated user files
vpn user info <name> [--no-qr]  # Print README.txt and optional terminal QR
vpn user export <name> [--zip] [--json]
vpn user usage [name] [--json]  # Per-user traffic counters
vpn user limit <name> (--quota-gb N | --quota-bytes N | --disable) [--json]
vpn user suspend <name> [--json]
vpn user resume <name> [--json]
vpn user reset-usage <name> [--json]
vpn sub [--json]                # Subscription server status and URLs
vpn panel                       # TTY panel; also opens on plain `vpn` in TTY
vpn status [--json]             # Services, ports, quotas and server load
vpn logs [service] [--json]     # Logs
vpn update                      # Update xray-core, hysteria and mtg
vpn uninstall [--yes]           # Full cleanup
vpn completion [bash|zsh]       # Shell completion snippet
```

Python entrypoint is still available:

```bash
python3 scripts/vpn_manager.py user list --json
python3 scripts/vpn_manager.py status --json
python3 scripts/vpn_manager.py panel
```

Shell completion:

```bash
eval "$(vpn completion bash)"
eval "$(vpn completion zsh)"
```

<a id="web-admin"></a>

### Web Admin

The public subscription endpoint remains public:

```text
http://SERVER:8000/sub/<name>
```

The admin UI is local-only by default:

```text
http://127.0.0.1:8081/
```

Access flow:

1. Open an SSH tunnel:
   ```bash
   ssh -L 8081:127.0.0.1:8081 root@SERVER
   ```
2. Open `http://127.0.0.1:8081/`
3. Authenticate with `VPN_PANEL_TOKEN` from `data/server.env`

Admin UI actions:

- create and delete users
- inspect generated configs and proxy credentials
- copy subscription URLs
- download ZIP bundles
- set quotas or disable them
- suspend and resume users
- reset traffic accounting
- watch CPU, RAM, disk and network load

Quota note:

- Traffic accounting uses Xray stats, so quota enforcement is most accurate for Xray-based profiles.

### Telegram Bot

Runs as `vpn-bot.service` and only responds to `ADMIN_CHAT_ID`.

| Command | Action |
|---|---|
| `/start` | Menu |
| `/add <name>` | Create user and send configs |
| `/del <name>` | Revoke user |
| `/list` | Show users |
| `/info <name>` | Resend bundle |
| `/status` | Show services status |
| `/logs` | Send recent logs |

<a id="security-defaults"></a>

### Security Defaults

- Admin UI binds to `127.0.0.1` by default and is not exposed publicly.
- Installer runs `scripts/install_security_hardening.sh`.
- `ufw` is configured with `default deny incoming`.
- `fail2ban` is enabled for SSH.
- SSH defaults to a root-only operational model.
- X11, agent forwarding and stream forwarding are disabled.
- Local service units get tighter systemd sandboxing.
- Runtime data and generated bundles get stricter file permissions.

If you do not want password-only root SSH, change:

- `VPN_SSH_PASSWORD_ONLY`
- `VPN_SSH_ALLOW_USERS`
- `/etc/ssh/sshd_config.d/90-vpn-hardening.conf`

### Advanced Bypass Modes

- Optional selective Cloudflare WARP egress for problematic domains such as Gemini and AI Studio.
- Curated rescue feeds and mirror links inspired by `igareck/vpn-configs-for-russia`.
- Multiple protocol fallbacks so one broken transport does not take down the whole node.

### Runtime Notes

- No external database required.
- State lives in `data/server.env`, `data/users.json` and `data/usage_state.json`.
- Shared generated configs are rendered into `data/generated/`.
- Subscription server returns base64 at `/sub/<name>` and plain text at `/sub/<name>/raw`.
- Xray API is enabled on `127.0.0.1:10085` for stats and control-plane integration.

### Secrets and Git Hygiene

- Do not commit real `data/server.env`.
- Do not commit real `data/users.json`.
- Do not commit `data/usage_state.json`.
- Use `data/server.env.example` and `data/users.json.example` as templates.
- Keep swap files and editor junk out of git.
- If secrets were tracked earlier:

```bash
git rm --cached data/server.env data/users.json
```

### Useful Links

#### Clients

- v2rayN: https://github.com/2dust/v2rayN
- Throne: https://github.com/throneproj/Throne
- Karing: https://github.com/KaringX/karing
- AmneziaVPN: https://github.com/amnezia-vpn/amnezia-client
- Happ: https://github.com/Happ-proxy
- Streisand: https://apps.apple.com/us/app/streisand/id6450534064
- Shadowrocket: https://apps.apple.com/us/app/shadowrocket/id932747118
- v2rayNG: https://github.com/2dust/v2rayNG
- NekoBox: https://github.com/MatsuriDayo/NekoBoxForAndroid

#### Server Components

- Xray-core: https://github.com/XTLS/Xray-core
- sing-box docs: https://sing-box.sagernet.org
- Hysteria2: https://github.com/apernet/hysteria
- mtg: https://github.com/9seconds/mtg
- WireGuard: https://www.wireguard.com

---

<a id="russian"></a>

## Русский

### Кратко

`vpn-deploy` это самодостаточный набор для развёртывания VPN и прокси на одном сервере. Он ставит стек, управляет пользователями, генерирует клиентские конфиги, отдает подписки, показывает нагрузку, умеет ограничивать трафик и дает две админские поверхности: CLI и локальную web-панель.

### Что здесь есть

- единая команда `vpn`
- Python control-plane без внешней БД
- web-админка с квотами, suspend/resume и скачиванием конфигов
- Telegram bot для admin-only операций
- несколько transport/fallback режимов
- hardened-by-default установка для публичного сервера

### Быстрый старт

```bash
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists
sudo ./install.sh
```

После установки:

```bash
vpn user add bob
vpn user info bob
vpn user export bob --zip
vpn status
```

### Основные команды

```bash
vpn user add <name>
vpn user del <name>
vpn user list
vpn user usage <name>
vpn user limit <name> --quota-gb 50
vpn user suspend <name>
vpn user resume <name>
vpn user reset-usage <name>
vpn status
vpn panel
vpn logs
```

### Структура проекта

```text
install.sh        -> общий installer
vpn.sh            -> thin wrapper для Python entrypoint
scripts/          -> install scripts, utils, vpn_manager.py
templates/        -> JSON/YAML/URI шаблоны
web/              -> frontend админки
sub_server.py     -> subscriptions + admin API/UI
bot.py            -> Telegram bot
data/             -> локальные runtime-данные
users/            -> пользовательские bundle и exports
tests/            -> тесты
```

### Веб-админка

- публичная подписка: `http://SERVER:8000/sub/<name>`
- админка по умолчанию: `http://127.0.0.1:8081/`
- доступ через SSH tunnel:

```bash
ssh -L 8081:127.0.0.1:8081 root@SERVER
```

В панели можно:

- создавать и удалять пользователей
- смотреть конфиги и прокси-данные
- скачивать ZIP bundle
- ставить лимиты трафика
- suspend/resume пользователей
- смотреть CPU, RAM, disk и network load

### Безопасность

- админка не публикуется наружу по умолчанию
- `ufw` включается с `deny incoming`
- `fail2ban` защищает SSH
- сервисы запускаются с более жесткими systemd sandbox-настройками
- чувствительные файлы в `data/` и `users/` получают более строгие права

### Поддерживаемый стек

- Xray-core
- Hysteria2
- WireGuard
- AmneziaWG
- 3proxy
- MTProto
- Telegram bot
- selective WARP egress

### Не коммитить в репозиторий

- реальные `data/server.env`
- реальные `data/users.json`
- `data/usage_state.json`
- любые приватные ключи, IP, пароли и боевые секреты

---

## Quality Checklist

- [ ] Smoke on systemd host: `vpn install` -> `vpn status` -> `vpn user add` -> `vpn user info` -> `vpn user export --zip`
- [ ] Fresh Ubuntu 22.04 install completes without errors
- [ ] `vpn user add bob` generates all files in `users/bob/`
- [ ] `curl http://IP:8000/sub/bob` returns base64
- [ ] Subscription imports into v2rayN
- [ ] Subscription imports into v2rayNG
- [ ] Subscription imports into Karing
- [ ] Subscription imports into Streisand
- [ ] Subscription imports into NekoBox
- [ ] VLESS Reality URI imports into Shadowrocket
- [ ] Hysteria2 URI imports into supported clients
- [ ] `xray_client.json` imports into AmneziaVPN-compatible clients
- [ ] `singbox_client.json` imports into Karing and NekoBox
- [ ] `awg.conf` imports into AmneziaVPN
- [ ] HTTP proxy works with `curl -x`
- [ ] SOCKS5 proxy works with `curl --socks5`
- [ ] MTProto link opens in Telegram
- [ ] `vpn user del bob` revokes access cleanly
- [ ] Bot `/add carol` sends the expected files and QR images
- [ ] Server remains within expected idle RAM budget
