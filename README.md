# vpn-deploy

[RU](#ru) | [EN](#en)

---

<a id="en"></a>

## EN — Lightweight Self-Hosted VPN/Proxy Toolkit

No web panel, no database, no billing. Installs protocols, manages users, generates client bundles: files, URIs, QR codes, or one subscription URL.

### Quick Start

```bash
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists
sudo ./install.sh
```

After install:

```bash
vpn user add bob
vpn user info bob
vpn user export bob --zip
vpn status
```

### What It Generates Per User

| File | Description |
|---|---|
| Subscription URL | `http://SERVER:8000/sub/<name>` — one link imports everything |
| `uris.txt` | VLESS Reality TCP, VLESS Reality XHTTP, VLESS WS, VLESS gRPC, VMess WS |
| `xray_client.json` | XRay outbound config (AmneziaVPN, v2rayN, Happ) |
| `singbox_client.json` | Sing-Box outbound config (Karing, NekoBox, Streisand, v2RayTun) |
| `wg.conf` | WireGuard config |
| `awg.conf` | AmneziaWG config |
| `proxy.txt` | HTTP + SOCKS5 proxy credentials |
| `mtproto.txt` | Telegram MTProto proxy links |
| `qr_*.png` | QR codes (subscription, VLESS, WireGuard) |
| `README.txt` | Human-readable setup guide per user |

### Supported Clients

| Client | Platform | Sub URL | URI | JSON | Notes |
|---|---|:---:|:---:|:---:|---|
| **v2rayN** | Win/Linux/macOS | ✅ | ✅ | Xray | Primary desktop |
| **Throne** | Win/Linux/macOS | ✅ | ✅ | Xray/SB | Nekoray successor |
| **Karing** | Win/Linux/macOS/iOS | ✅ | ✅ | Sing-Box | |
| **AmneziaVPN** | Win/Linux/macOS/iOS/Android | — | ✅ | Xray/WG/AWG | File import |
| **Happ** | macOS/iOS/tvOS | ✅ | ✅ | Xray | `vless://`, `vmess://`, JSON |
| **Streisand** | iOS | ✅ | ✅ | Sing-Box | Primary iOS |
| **Shadowrocket** | iOS | ✅ | ✅ | — | VLESS Reality URI |
| **V2Box** | iOS/Android | ✅ | ✅ | — | |
| **v2RayTun** | iOS/Android | ✅ | ✅ | Sing-Box | |
| **v2rayNG** | Android | ✅ | ✅ | — | Primary Android |
| **NekoBox** | Android | ✅ | ✅ | Sing-Box | |

### Supported Protocols

| # | Protocol | Port | Purpose |
|---|---|---|---|
| 1 | VLESS + XTLS-Reality (TCP) | 443 | Primary, best DPI bypass |
| 2 | VLESS + Reality (XHTTP) | 8443 | HTTP-masked fallback |
| 3 | VLESS + WS | 8444 | WebSocket fallback |
| 4 | VLESS + gRPC | 8445 | gRPC fallback |
| 5 | VMess + WS | 8446 | Legacy wide support |
| 6 | AmneziaWG | 51820 | Obfuscated WireGuard |
| 7 | WireGuard | 51820 | Plain fallback |
| 8 | HTTP proxy (3proxy) | 8080 | Browser/curl |
| 9 | SOCKS5 proxy (3proxy) | 1080 | Browser/curl |
| 10 | MTProto (mtg v2) | 8447 | Telegram native proxy |

### CLI

```bash
vpn install                     # Interactive setup wizard
vpn user add <name>             # Create user, generate ALL configs
vpn user del <name>             # Revoke user from all services
vpn user list                   # Table: name | created | protocols | sub URL
vpn user info <name>            # Print README.txt + QR codes to terminal
vpn user export <name> [--zip]  # Output files or zip archive
vpn sub                         # Subscription server status + all URLs
vpn status                      # All services status, ports, peer counts
vpn logs [service]              # Tail logs
vpn update                      # Update xray-core and mtg binaries
vpn uninstall                   # Full cleanup
```

### Telegram Bot

Single file, runs as `vpn-bot.service`. Only responds to `ADMIN_CHAT_ID`.

| Command | Action |
|---|---|
| `/start` | Menu |
| `/add <name>` | Create user, send all configs + QR + sub URL |
| `/del <name>` | Revoke user |
| `/list` | User table |
| `/info <name>` | Resend all configs |
| `/status` | Services status |
| `/logs` | Last 50 lines |

### Project Notes

- No Docker required for core flow
- State stored in `data/users.json` and `data/server.env`
- Shared service configs rendered into `data/generated/`
- Subscription server returns base64 at `/sub/<name>`, plain text at `/sub/<name>/raw`
- Xray API enabled on 127.0.0.1:10085 for future hot-reload
- Idle RAM target: < 60 MB

---

<a id="ru"></a>

## RU — Лёгкий инструмент для самостоятельного развёртывания VPN/прокси

Без веб-панели, без базы данных, без биллинга. Устанавливает протоколы, управляет пользователями, генерирует клиентские конфиги: файлы, URI, QR-коды или одну ссылку подписки.

### Быстрый старт

```bash
git clone https://github.com/parasha3a/VPN-Proxy_for_Bypassing_Whitelists.git
cd VPN-Proxy_for_Bypassing_Whitelists
sudo ./install.sh
```

После установки:

```bash
vpn user add bob      # Создать пользователя и все конфиги
vpn user info bob     # Показать README + QR-коды
vpn user list         # Список всех пользователей
vpn status            # Статус всех сервисов
```

### Что генерируется на пользователя

- **Subscription URL** `http://SERVER:8000/sub/<name>` — одна ссылка импортирует всё
- **uris.txt** — все URI (VLESS Reality, XHTTP, WS, gRPC, VMess)
- **xray_client.json** — для AmneziaVPN, v2rayN, Happ
- **singbox_client.json** — для Karing, NekoBox, Streisand, v2RayTun
- **wg.conf / awg.conf** — WireGuard / AmneziaWG
- **proxy.txt** — HTTP + SOCKS5 прокси
- **mtproto.txt** — ссылки для Telegram
- **QR-коды** — PNG файлы для мобильного импорта

### Поддерживаемые клиенты

**Десктоп:** v2rayN, Throne, Karing, AmneziaVPN, Happ

**iOS:** Streisand, Shadowrocket, Karing, V2Box, v2RayTun, Happ

**Android:** v2rayNG, NekoBox, v2Box, v2RayTun

**Telegram:** встроенный MTProto прокси

### Поддерживаемые протоколы

1. VLESS + XTLS-Reality (TCP) — основной, порт 443, лучший обход DPI (РКН/белые списки)
2. VLESS + Reality (XHTTP) — fallback через HTTP
3. VLESS + WS — WebSocket fallback
4. VLESS + gRPC — gRPC fallback
5. VMess + WS — legacy, широкая поддержка
6. AmneziaWG — обфусцированный WireGuard
7. WireGuard — обычный
8. HTTP прокси (3proxy) — порт 8080
9. SOCKS5 прокси (3proxy) — порт 1080
10. MTProto (mtg v2) — порт 8447, для Telegram

### CLI команды

```bash
vpn install                     # Интерактивный мастер установки
vpn user add <name>             # Создать пользователя и ВСЕ конфиги
vpn user del <name>             # Удалить пользователя из всех сервисов
vpn user list                   # Таблица пользователей
vpn user info <name>            # Показать README.txt + QR-коды
vpn user export <name> [--zip]  # Экспорт файлов или zip-архив
vpn sub                         # Статус сервера подписок
vpn status                      # Статус всех сервисов
vpn logs [service]              # Логи
vpn update                      # Обновить xray-core и mtg
vpn uninstall                   # Полная очистка
```

---

## Documentation / Документация

### Desktop Clients

- **v2rayN** — [GitHub](https://github.com/2dust/v2rayN) · [Wiki](https://github.com/2dust/v2rayN/wiki) · [Releases](https://github.com/2dust/v2rayN/releases)
- **Throne** — [GitHub](https://github.com/throneproj/Throne) · [Docs](https://throneproj.github.io/introduction/) · [Releases](https://github.com/throneproj/Throne/releases)
- **Karing** — [GitHub](https://github.com/KaringX/karing) · [Site](https://karing.app) · [Releases](https://github.com/KaringX/karing/releases)
- **AmneziaVPN** — [GitHub](https://github.com/amnezia-vpn/amnezia-client) · [Docs](https://docs.amnezia.org) · [Config formats](https://docs.amnezia.org/documentation/supported-configuration-formats/) · [XRay](https://docs.amnezia.org/documentation/xray/) · [AmneziaWG](https://docs.amnezia.org/documentation/how-amnezia-works/)
- **Happ** — [GitHub](https://github.com/Happ-proxy) · [Desktop](https://github.com/Happ-proxy/happ-desktop) · [iOS](https://github.com/Happ-proxy/happ-ios) · [Android](https://github.com/Happ-proxy/happ-android) · [Docs](https://github.com/Flyfrog-LLC/Happ-docs) · [Site](https://happ.su)

### iOS Clients

- **Streisand** — [App Store](https://apps.apple.com/us/app/streisand/id6450534064)
- **Shadowrocket** — [App Store](https://apps.apple.com/us/app/shadowrocket/id932747118) · [Wiki](https://github.com/Shadowrocket/Wiki) · [Manual](https://github.com/Shadowrocket/manual)
- **Karing** — [App Store](https://apps.apple.com/us/app/karing/id6472431552) · [TestFlight](https://testflight.apple.com/join/RLU59OsJ)
- **V2Box** — [App Store](https://apps.apple.com/us/app/v2box-v2ray-client/id6446814690)
- **v2RayTun** — [App Store](https://apps.apple.com/us/app/v2raytun/id6476628951)

### Android Clients

- **v2rayNG** — [GitHub](https://github.com/2dust/v2rayNG) · [Wiki](https://github.com/2dust/v2rayNG/wiki) · [Google Play](https://play.google.com/store/apps/details?id=com.v2ray.ang)
- **NekoBox** — [GitHub](https://github.com/MatsuriDayo/NekoBoxForAndroid) · [Docs](https://matsuridayo.github.io)
- **v2Box** — [Google Play](https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box)
- **v2RayTun** — [Google Play](https://play.google.com/store/apps/details?id=com.v2raytun.android)

### Server Components

- **Xray-core** — [GitHub](https://github.com/XTLS/Xray-core) · [Docs](https://xtls.github.io/en/) · [Config](https://xtls.github.io/en/config/) · [REALITY](https://github.com/XTLS/REALITY) · [Examples](https://github.com/XTLS/Xray-examples) · [Installer](https://github.com/XTLS/Xray-install)
- **sing-box** — [GitHub](https://github.com/SagerNet/sing-box) · [Docs](https://sing-box.sagernet.org) · [Config](https://sing-box.sagernet.org/configuration/)
- **AmneziaWG** — [GitHub](https://github.com/amnezia-vpn/amnezia-wg)
- **mtg** — [GitHub](https://github.com/9seconds/mtg) · [Releases](https://github.com/9seconds/mtg/releases)

---

## Quality Checklist

- [ ] Fresh Ubuntu 22.04: one-liner install completes without errors
- [ ] `vpn user add bob` generates all files in `users/bob/`
- [ ] `curl http://IP:8000/sub/bob` returns base64
- [ ] Subscription imports into v2rayN
- [ ] Subscription imports into v2rayNG
- [ ] Subscription imports into Karing
- [ ] Subscription imports into Streisand
- [ ] Subscription imports into NekoBox
- [ ] VLESS Reality URI imports into Shadowrocket
- [ ] VLESS Reality URI imports into Happ (iOS + macOS)
- [ ] `xray_client.json` imports into AmneziaVPN
- [ ] `xray_client.json` imports into Happ
- [ ] `singbox_client.json` imports into Karing and NekoBox
- [ ] `awg.conf` imports into AmneziaVPN
- [ ] HTTP proxy works with `curl -x`
- [ ] SOCKS5 proxy works with `curl --socks5`
- [ ] MTProto link opens in Telegram
- [ ] `vpn user del bob` removes access cleanly
- [ ] Bot `/add carol` sends the expected files and QR images
- [ ] Idle RAM stays below 60 MB
- [ ] README.md in RU + EN with install command + app compatibility table
