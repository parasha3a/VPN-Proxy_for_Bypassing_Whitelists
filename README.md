# vpn-deploy

RU | EN

Lightweight self-hosted VPN/proxy toolkit for a personal VPS. No web panel, no database, no billing logic. It installs protocols, manages users, and generates client bundles that can be shared as files, URIs, QR codes, or one subscription URL.

## Install

```bash
git clone https://github.com/your-org/vpn-deploy.git
cd vpn-deploy
sudo ./install.sh
```

After install:

```bash
vpn user add bob
vpn user info bob
vpn user export bob --zip
vpn status
```

## What It Generates Per User

- Subscription URL on `http://SERVER:8000/sub/<name>`
- `uris.txt` with VLESS Reality TCP, VLESS Reality XHTTP, VLESS WS, VLESS gRPC, VMess WS
- `xray_client.json`
- `singbox_client.json`
- `wg.conf`
- `awg.conf`
- `proxy.txt`
- `mtproto.txt`
- QR PNG files
- `README.txt`

## Supported Clients

| Client | Subscription URL | URI import | JSON import | Notes |
|---|---|---:|---:|---|
| v2rayN | Yes | Yes | Xray JSON | Primary desktop target |
| Throne | Yes | Yes | Xray/Sing-Box style | Alternative desktop target |
| Karing | Yes | Yes | Sing-Box JSON | Desktop + iOS |
| AmneziaVPN | Partial | Yes | Xray JSON / WG / AWG | Imports config files directly |
| Streisand | Yes | Yes | Sing-Box JSON | Primary iOS target |
| Shadowrocket | Yes | Yes | Partial | VLESS Reality URI target |
| v2rayNG | Yes | Yes | Partial | Primary Android target |
| NekoBox | Yes | Yes | Sing-Box JSON | Secondary Android target |
| V2Box | Yes | Yes | Partial | Mobile target |
| v2RayTun | Yes | Yes | Sing-Box JSON | Mobile target |
| Happ | Yes | Yes | Xray JSON | Experimental compatibility |

## Default Stack

- Xray-core: VLESS Reality TCP, VLESS Reality XHTTP, VLESS WS, VLESS gRPC, VMess WS
- WireGuard
- AmneziaWG config generation
- 3proxy for HTTP and SOCKS5
- mtg v2 for Telegram MTProto
- Python subscription server
- Optional Telegram bot

## CLI

```bash
vpn install
vpn user add <name>
vpn user del <name>
vpn user list
vpn user info <name>
vpn user export <name> [--zip]
vpn sub
vpn status
vpn logs [service]
vpn update
vpn uninstall
```

## Project Notes

- No Docker is required for the core flow.
- No database is used; state is stored in `data/users.json` and `data/server.env`.
- Shared service configs are rendered into `data/generated/`.
- The subscription server returns base64-encoded raw URI lines at `/sub/<name>` and plain text at `/sub/<name>/raw`.
- Xray API is enabled for future hot-user operations, but this repository currently applies config regeneration plus service restart for server-side sync.
- `vpn-configs-for-russia` influenced the subscription-first delivery model and cross-client compatibility assumptions.
- `miniature-octo-palm-tree` influenced the Reality/XHTTP transport choices and key generation approach with `xray uuid` and `xray x25519`.

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

## RU Summary

- Минимальный стек без панели и БД.
- Основной формат доставки: subscription URL.
- На пользователя генерируются URI, JSON, WG/AWG, прокси-данные, MTProto-ссылки и QR-коды.
- Поддерживаются v2rayN, Throne, Karing, Streisand, Shadowrocket, v2rayNG, NekoBox, AmneziaVPN и Happ.
