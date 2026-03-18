#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import secrets
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
USERS_DIR = ROOT / "users"
GENERATED_DIR = DATA_DIR / "generated"
USERS_DB_PATH = DATA_DIR / "users.json"
SERVER_ENV_PATH = DATA_DIR / "server.env"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_layout() -> None:
    for path in (DATA_DIR, USERS_DIR, GENERATED_DIR):
        path.mkdir(parents=True, exist_ok=True)
    if not USERS_DB_PATH.exists():
        USERS_DB_PATH.write_text(json.dumps({"users": {}}, indent=2) + "\n")
    if not SERVER_ENV_PATH.exists():
        raise SystemExit("missing data/server.env, run vpn.sh once or create the file")


def load_env() -> dict[str, str]:
    ensure_layout()
    env: dict[str, str] = {}
    for line in SERVER_ENV_PATH.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def load_db() -> dict[str, Any]:
    ensure_layout()
    with USERS_DB_PATH.open() as fh:
        data = json.load(fh)
    data.setdefault("users", {})
    return data


def save_db(data: dict[str, Any]) -> None:
    USERS_DB_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def sanitize_name(name: str) -> str:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip("-_")
    if not safe:
        raise SystemExit("invalid user name")
    return safe


def random_hex(length: int) -> str:
    return secrets.token_hex(length // 2)


def random_b64(length: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(length)).decode()


def command_output(*cmd: str, input_text: str | None = None) -> str:
    proc = subprocess.run(
        list(cmd),
        input=None if input_text is None else input_text.encode(),
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().strip()


def generate_wg_material() -> tuple[str, str, str]:
    try:
        private_key = command_output("wg", "genkey")
        public_key = command_output("wg", "pubkey", input_text=private_key)
        psk = command_output("wg", "genpsk")
        return private_key, public_key, psk
    except Exception:
        return random_b64(), random_b64(), random_b64()


def encode_uri_fragment(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def encode_query_path(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="/")


def encode_userinfo(value: str, keep_colon: bool = False) -> str:
    from urllib.parse import quote

    return quote(value, safe=":" if keep_colon else "")


def next_client_ips(users: dict[str, Any], env: dict[str, str]) -> tuple[str, str]:
    taken_v4: set[int] = set()
    taken_v6: set[int] = set()
    v4_net = ipaddress.ip_network(env["WG_CLIENT_NET"], strict=False)
    v6_net = ipaddress.ip_network(env["WG_CLIENT_NET6"], strict=False)

    for user in users.values():
        if "wg_ipv4" in user:
            taken_v4.add(int(ipaddress.ip_interface(user["wg_ipv4"]).ip))
        if "wg_ipv6" in user:
            taken_v6.add(int(ipaddress.ip_interface(user["wg_ipv6"]).ip))

    for offset in range(2, v4_net.num_addresses - 1):
        candidate_v4 = int(v4_net.network_address) + offset
        candidate_v6 = int(v6_net.network_address) + offset
        if candidate_v4 not in taken_v4 and candidate_v6 not in taken_v6:
            ipv4 = f"{ipaddress.ip_address(candidate_v4)}/{v4_net.prefixlen}"
            ipv6 = f"{ipaddress.ip_address(candidate_v6)}/{v6_net.prefixlen}"
            return ipv4, ipv6
    raise SystemExit("no free WireGuard addresses left")


def subscription_url(env: dict[str, str], name: str) -> str:
    host = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    return f"http://{host}:{env['SUB_PORT']}/sub/{name}"


def build_user_record(name: str, users: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    wg_private, wg_public, wg_psk = generate_wg_material()
    wg_ipv4, wg_ipv6 = next_client_ips(users, env)
    proxy_password = secrets.token_urlsafe(12)
    return {
        "name": name,
        "created": now_utc(),
        "uuid": str(uuid.uuid4()),
        "email": f"{name}@vpn.local",
        "proxy_username": name,
        "proxy_password": proxy_password,
        "hy2_username": name,
        "hy2_password": secrets.token_urlsafe(16),
        "wg_private_key": wg_private,
        "wg_public_key": wg_public,
        "wg_preshared_key": wg_psk,
        "wg_ipv4": wg_ipv4,
        "wg_ipv6": wg_ipv6,
    }


def build_hy2_uri(user: dict[str, Any], env: dict[str, str]) -> str:
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    auth = encode_userinfo(f"{user['hy2_username']}:{user['hy2_password']}", keep_colon=True)
    label = f"{encode_uri_fragment(env.get('SERVER_NAME', 'VPN'))}-{encode_uri_fragment(user['name'])}-Hysteria2"
    query = [
        f"obfs=salamander",
        f"obfs-password={encode_userinfo(env['HY2_OBFS_PASSWORD'])}",
        f"sni={encode_userinfo(env['HY2_TLS_SNI'])}",
        "insecure=1",
    ]
    if env.get("HY2_PIN_SHA256") and env["HY2_PIN_SHA256"] != "CHANGE_ME":
        query.append(f"pinSHA256={encode_userinfo(env['HY2_PIN_SHA256'])}")
    return f"hysteria2://{auth}@{server}:{env['HY2_PORT']}/?{'&'.join(query)}#{label}"


def build_uris(user: dict[str, Any], env: dict[str, str]) -> list[str]:
    name = user["name"]
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    label_prefix = encode_uri_fragment(env.get("SERVER_NAME", "VPN"))
    shared = f"{label_prefix}-{encode_uri_fragment(name)}"
    path_xhttp = encode_query_path(env["XRAY_XHTTP_PATH"])
    path_ws = encode_query_path(env["XRAY_WS_PATH"])
    path_vmess = env["XRAY_VMESS_WS_PATH"]

    vless_reality = (
        f"vless://{user['uuid']}@{server}:{env['XRAY_PORT_REALITY']}"
        f"?encryption=none&flow=xtls-rprx-vision&security=reality"
        f"&sni={env['XRAY_REALITY_SNI']}&fp={env['XRAY_REALITY_FINGERPRINT']}"
        f"&pbk={env['XRAY_REALITY_PUBLIC_KEY']}&sid={env['XRAY_REALITY_SHORT_ID']}"
        f"&type=tcp#{shared}-Reality"
    )
    vless_xhttp = (
        f"vless://{user['uuid']}@{server}:{env['XRAY_PORT_XHTTP']}"
        f"?encryption=none&security=reality&sni={env['XRAY_REALITY_SNI']}"
        f"&fp={env['XRAY_REALITY_FINGERPRINT']}&pbk={env['XRAY_REALITY_PUBLIC_KEY']}"
        f"&sid={env['XRAY_REALITY_SHORT_ID']}&type=xhttp&path={path_xhttp}"
        f"#{shared}-Reality-XHTTP"
    )
    vless_ws = (
        f"vless://{user['uuid']}@{server}:{env['XRAY_PORT_WS']}"
        f"?encryption=none&security=none&type=ws&host={server}&path={path_ws}"
        f"#{shared}-WS"
    )
    vless_grpc = (
        f"vless://{user['uuid']}@{server}:{env['XRAY_PORT_GRPC']}"
        f"?encryption=none&security=none&type=grpc&serviceName={env['XRAY_GRPC_SERVICE']}"
        f"#{shared}-gRPC"
    )
    vmess_payload = {
        "v": "2",
        "ps": f"{env.get('SERVER_NAME', 'VPN')}-{name}-VMess-WS",
        "add": server,
        "port": env["XRAY_PORT_VMESS"],
        "id": user["uuid"],
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": server,
        "path": path_vmess,
        "tls": "",
        "sni": "",
        "alpn": "",
        "fp": env["XRAY_REALITY_FINGERPRINT"],
    }
    vmess = (
        "vmess://"
        + base64.b64encode(json.dumps(vmess_payload, separators=(",", ":")).encode()).decode()
        + f"#{shared}-VMess-WS"
    )
    return [vless_reality, vless_xhttp, vless_ws, vless_grpc, vmess, build_hy2_uri(user, env)]


def xray_outbounds(user: dict[str, Any], env: dict[str, str]) -> list[dict[str, Any]]:
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    return [
        {
            "protocol": "vless",
            "tag": "vless-reality-tcp",
            "settings": {
                "vnext": [
                    {
                        "address": server,
                        "port": int(env["XRAY_PORT_REALITY"]),
                        "users": [
                            {
                                "id": user["uuid"],
                                "encryption": "none",
                                "flow": "xtls-rprx-vision",
                            }
                        ],
                    }
                ]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "serverName": env["XRAY_REALITY_SNI"],
                    "publicKey": env["XRAY_REALITY_PUBLIC_KEY"],
                    "shortId": env["XRAY_REALITY_SHORT_ID"],
                    "fingerprint": env["XRAY_REALITY_FINGERPRINT"],
                },
            },
        },
        {
            "protocol": "vless",
            "tag": "vless-xhttp",
            "settings": {
                "vnext": [
                    {
                        "address": server,
                        "port": int(env["XRAY_PORT_XHTTP"]),
                        "users": [{"id": user["uuid"], "encryption": "none"}],
                    }
                ]
            },
            "streamSettings": {
                "network": "xhttp",
                "security": "reality",
                "xhttpSettings": {"path": env["XRAY_XHTTP_PATH"]},
                "realitySettings": {
                    "serverName": env["XRAY_REALITY_SNI"],
                    "publicKey": env["XRAY_REALITY_PUBLIC_KEY"],
                    "shortId": env["XRAY_REALITY_SHORT_ID"],
                    "fingerprint": env["XRAY_REALITY_FINGERPRINT"],
                },
            },
        },
        {
            "protocol": "vless",
            "tag": "vless-ws",
            "settings": {
                "vnext": [
                    {
                        "address": server,
                        "port": int(env["XRAY_PORT_WS"]),
                        "users": [{"id": user["uuid"], "encryption": "none"}],
                    }
                ]
            },
            "streamSettings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {"path": env["XRAY_WS_PATH"], "headers": {"Host": server}},
            },
        },
        {
            "protocol": "vless",
            "tag": "vless-grpc",
            "settings": {
                "vnext": [
                    {
                        "address": server,
                        "port": int(env["XRAY_PORT_GRPC"]),
                        "users": [{"id": user["uuid"], "encryption": "none"}],
                    }
                ]
            },
            "streamSettings": {
                "network": "grpc",
                "security": "none",
                "grpcSettings": {"serviceName": env["XRAY_GRPC_SERVICE"]},
            },
        },
        {
            "protocol": "vmess",
            "tag": "vmess-ws",
            "settings": {
                "vnext": [
                    {
                        "address": server,
                        "port": int(env["XRAY_PORT_VMESS"]),
                        "users": [{"id": user["uuid"], "security": "auto"}],
                    }
                ]
            },
            "streamSettings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {"path": env["XRAY_VMESS_WS_PATH"], "headers": {"Host": server}},
            },
        },
    ]


def build_xray_client(user: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {"tag": "socks-in", "listen": "127.0.0.1", "port": 10808, "protocol": "socks", "settings": {"udp": True}},
            {"tag": "http-in", "listen": "127.0.0.1", "port": 10809, "protocol": "http", "settings": {}},
        ],
        "outbounds": xray_outbounds(user, env)
        + [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "network": "tcp,udp", "outboundTag": "vless-reality-tcp"}],
        },
    }


def singbox_proxy_tags() -> list[str]:
    return ["vless-reality-tcp", "vless-xhttp", "vless-ws", "vless-grpc", "vmess-ws", "hysteria2"]


def build_singbox_client(user: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    fingerprint = env["XRAY_REALITY_FINGERPRINT"]
    reality_tls = {
        "enabled": True,
        "server_name": env["XRAY_REALITY_SNI"],
        "utls": {"enabled": True, "fingerprint": fingerprint},
        "reality": {
            "enabled": True,
            "public_key": env["XRAY_REALITY_PUBLIC_KEY"],
            "short_id": env["XRAY_REALITY_SHORT_ID"],
        },
    }
    outbounds: list[dict[str, Any]] = [
        {
            "type": "selector",
            "tag": "select",
            "outbounds": ["auto", *singbox_proxy_tags(), "direct"],
            "default": "auto",
        },
        {
            "type": "urltest",
            "tag": "auto",
            "outbounds": singbox_proxy_tags(),
            "url": "https://www.gstatic.com/generate_204",
            "interval": "10m",
            "tolerance": 50,
        },
        {
            "type": "vless",
            "tag": "vless-reality-tcp",
            "server": server,
            "server_port": int(env["XRAY_PORT_REALITY"]),
            "uuid": user["uuid"],
            "flow": "xtls-rprx-vision",
            "packet_encoding": "xudp",
            "tls": reality_tls,
        },
        {
            "type": "vless",
            "tag": "vless-xhttp",
            "server": server,
            "server_port": int(env["XRAY_PORT_XHTTP"]),
            "uuid": user["uuid"],
            "tls": reality_tls,
            "transport": {
                "type": "http",
                "host": [env["XRAY_REALITY_SNI"]],
                "path": env["XRAY_XHTTP_PATH"],
            },
        },
        {
            "type": "vless",
            "tag": "vless-ws",
            "server": server,
            "server_port": int(env["XRAY_PORT_WS"]),
            "uuid": user["uuid"],
            "transport": {"type": "ws", "path": env["XRAY_WS_PATH"], "headers": {"Host": server}},
        },
        {
            "type": "vless",
            "tag": "vless-grpc",
            "server": server,
            "server_port": int(env["XRAY_PORT_GRPC"]),
            "uuid": user["uuid"],
            "transport": {"type": "grpc", "service_name": env["XRAY_GRPC_SERVICE"]},
        },
        {
            "type": "vmess",
            "tag": "vmess-ws",
            "server": server,
            "server_port": int(env["XRAY_PORT_VMESS"]),
            "uuid": user["uuid"],
            "security": "auto",
            "transport": {"type": "ws", "path": env["XRAY_VMESS_WS_PATH"], "headers": {"Host": server}},
        },
        {
            "type": "hysteria2",
            "tag": "hysteria2",
            "server": server,
            "server_port": int(env["HY2_PORT"]),
            "up_mbps": int(env["HY2_UP_MBPS"]),
            "down_mbps": int(env["HY2_DOWN_MBPS"]),
            "password": f"{user['hy2_username']}:{user['hy2_password']}",
            "obfs": {"type": "salamander", "password": env["HY2_OBFS_PASSWORD"]},
            "tls": {
                "enabled": True,
                "server_name": env["HY2_TLS_SNI"],
                "insecure": True,
                "alpn": ["h3"],
            },
        },
        {"type": "direct", "tag": "direct"},
        {"type": "block", "tag": "block"},
    ]
    return {
        "log": {"level": "warn"},
        "inbounds": [{"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2080}],
        "outbounds": outbounds,
        "route": {"auto_detect_interface": True, "final": "select"},
    }


def build_wg_client(user: dict[str, Any], env: dict[str, str]) -> str:
    endpoint = f"{env.get('SERVER_HOST') or env.get('SERVER_IP')}:{env['WG_SERVER_PORT']}"
    return "\n".join(
        [
            "[Interface]",
            f"PrivateKey = {user['wg_private_key']}",
            f"Address = {user['wg_ipv4']}, {user['wg_ipv6']}",
            f"DNS = {env['WG_DNS']}",
            "",
            "[Peer]",
            f"PublicKey = {env['WG_SERVER_PUBLIC_KEY']}",
            f"PresharedKey = {user['wg_preshared_key']}",
            "AllowedIPs = 0.0.0.0/0, ::/0",
            f"Endpoint = {endpoint}",
            "PersistentKeepalive = 25",
            "",
        ]
    )


def build_awg_client(user: dict[str, Any], env: dict[str, str]) -> str:
    base = build_wg_client(user, env).rstrip()
    extras = [
        f"Jc = {env['AWG_JC']}",
        f"Jmin = {env['AWG_JMIN']}",
        f"Jmax = {env['AWG_JMAX']}",
        f"S1 = {env['AWG_S1']}",
        f"S2 = {env['AWG_S2']}",
        f"H1 = {env['AWG_H1']}",
        f"H2 = {env['AWG_H2']}",
        f"H3 = {env['AWG_H3']}",
        f"H4 = {env['AWG_H4']}",
        "",
    ]
    return base + "\n" + "\n".join(extras)


def build_proxy_txt(user: dict[str, Any], env: dict[str, str]) -> str:
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    return (
        f"HTTP:   http://{user['proxy_username']}:{user['proxy_password']}@{server}:{env['HTTP_PROXY_PORT']}\n"
        f"SOCKS5: socks5://{user['proxy_username']}:{user['proxy_password']}@{server}:{env['SOCKS5_PROXY_PORT']}\n"
    )


def build_mtproto_txt(env: dict[str, str]) -> str:
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    return (
        f"tg://proxy?server={server}&port={env['MTPROTO_PORT']}&secret={env['MTPROTO_SECRET']}\n"
        f"https://t.me/proxy?server={server}&port={env['MTPROTO_PORT']}&secret={env['MTPROTO_SECRET']}\n"
    )


def build_hy2_client(user: dict[str, Any], env: dict[str, str]) -> str:
    server = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    lines = [
        f"server: {server}:{env['HY2_PORT']}",
        f"auth: {user['hy2_username']}:{user['hy2_password']}",
        "tls:",
        f"  sni: {env['HY2_TLS_SNI']}",
        "  insecure: true",
    ]
    if env.get("HY2_PIN_SHA256") and env["HY2_PIN_SHA256"] != "CHANGE_ME":
        lines.append(f"  pinSHA256: {env['HY2_PIN_SHA256']}")
    lines.extend(
        [
            "obfs:",
            "  type: salamander",
            "  salamander:",
            f"    password: {env['HY2_OBFS_PASSWORD']}",
            "bandwidth:",
            f"  up: {env['HY2_UP_MBPS']} mbps",
            f"  down: {env['HY2_DOWN_MBPS']} mbps",
            "socks5:",
            "  listen: 127.0.0.1:1080",
            "http:",
            "  listen: 127.0.0.1:1081",
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(user: dict[str, Any], env: dict[str, str], uris: list[str]) -> str:
    lines = [
        f"=== VPN Configs for: {user['name']} ===",
        f"Generated: {today_local()}",
        "",
        "[SUBSCRIPTION URL - recommended, imports everything at once]",
        subscription_url(env, user["name"]),
        "",
        "[QUICK IMPORT by app]",
        "v2rayN / Throne / Karing / Happ (Windows/Linux/macOS):",
        "-> Add subscription URL above via Ctrl+V or subscription import",
        "v2rayNG / NekoBox / v2Box / v2RayTun (Android):",
        "-> Add subscription URL above",
        "Streisand / Shadowrocket / Karing / V2Box / v2RayTun / Happ (iOS):",
        "-> Add subscription URL above",
        "AmneziaVPN:",
        "-> Import xray_client.json  (for VLESS Reality and fallbacks)",
        "-> Import awg.conf          (for AmneziaWG)",
        "-> Import wg.conf           (for WireGuard)",
        "Hysteria2-compatible apps:",
        "-> Import the hysteria2:// URI from uris.txt or use hy2_client.yaml",
        "Telegram MTProto:",
        "-> Click a link from mtproto.txt or share it in chat",
        "HTTP/SOCKS5 Proxy:",
        "-> See proxy.txt",
        "",
        "[ALL SHAREABLE URIS]",
        *uris,
        "",
    ]
    return "\n".join(lines)


def maybe_qr_png(payload: str, output: Path) -> None:
    try:
        subprocess.run(["qrencode", "-o", str(output), payload], check=True, capture_output=True)
    except Exception:
        pass


def write_user_bundle(user: dict[str, Any], env: dict[str, str]) -> None:
    user_dir = USERS_DIR / user["name"]
    user_dir.mkdir(parents=True, exist_ok=True)
    uris = build_uris(user, env)
    raw_uris = "\n".join(uris) + "\n"
    sub_b64 = base64.b64encode(raw_uris.encode()).decode()
    sub_url = subscription_url(env, user["name"])

    (user_dir / "uris.txt").write_text(raw_uris)
    (user_dir / "subscription.b64").write_text(sub_b64 + "\n")
    (user_dir / "subscription_url.txt").write_text(sub_url + "\n")
    (user_dir / "xray_client.json").write_text(json.dumps(build_xray_client(user, env), indent=2) + "\n")
    (user_dir / "singbox_client.json").write_text(json.dumps(build_singbox_client(user, env), indent=2) + "\n")
    (user_dir / "hy2_client.yaml").write_text(build_hy2_client(user, env))
    (user_dir / "wg.conf").write_text(build_wg_client(user, env))
    (user_dir / "awg.conf").write_text(build_awg_client(user, env))
    (user_dir / "proxy.txt").write_text(build_proxy_txt(user, env))
    (user_dir / "mtproto.txt").write_text(build_mtproto_txt(env))
    (user_dir / "README.txt").write_text(build_readme(user, env, uris))

    maybe_qr_png(uris[0], user_dir / "qr_vless.png")
    maybe_qr_png((user_dir / "wg.conf").read_text(), user_dir / "qr_wg.png")
    maybe_qr_png(sub_url, user_dir / "qr_sub.png")


def xray_server_user(user: dict[str, Any], with_flow: bool) -> dict[str, Any]:
    entry = {"id": user["uuid"], "email": user["email"]}
    if with_flow:
        entry["flow"] = "xtls-rprx-vision"
    return entry


def build_xray_server(users: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    users_list = list(users.values())
    vless_users = [xray_server_user(user, with_flow=False) for user in users_list]
    reality_users = [xray_server_user(user, with_flow=True) for user in users_list]
    vmess_users = [{"id": user["uuid"], "email": user["email"]} for user in users_list]
    return {
        "log": {"loglevel": "warning"},
        "api": {
            "tag": "api",
            "listen": env["XRAY_API_LISTEN"],
            "services": ["HandlerService", "LoggerService", "StatsService", "ReflectionService"],
        },
        "stats": {},
        "policy": {
            "levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}},
            "system": {"statsInboundUplink": True, "statsInboundDownlink": True},
        },
        "inbounds": [
            {
                "tag": "vless-reality-tcp",
                "listen": "0.0.0.0",
                "port": int(env["XRAY_PORT_REALITY"]),
                "protocol": "vless",
                "settings": {"clients": reality_users, "decryption": "none"},
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "target": env["XRAY_REALITY_TARGET"],
                        "serverNames": [env["XRAY_REALITY_SNI"]],
                        "privateKey": env["XRAY_REALITY_PRIVATE_KEY"],
                        "shortIds": [env["XRAY_REALITY_SHORT_ID"]],
                    },
                },
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
            },
            {
                "tag": "vless-xhttp",
                "listen": "0.0.0.0",
                "port": int(env["XRAY_PORT_XHTTP"]),
                "protocol": "vless",
                "settings": {"clients": vless_users, "decryption": "none"},
                "streamSettings": {
                    "network": "xhttp",
                    "security": "reality",
                    "xhttpSettings": {"path": env["XRAY_XHTTP_PATH"]},
                    "realitySettings": {
                        "target": env["XRAY_REALITY_TARGET"],
                        "serverNames": [env["XRAY_REALITY_SNI"]],
                        "privateKey": env["XRAY_REALITY_PRIVATE_KEY"],
                        "shortIds": [env["XRAY_REALITY_SHORT_ID"]],
                    },
                },
            },
            {
                "tag": "vless-ws",
                "listen": "0.0.0.0",
                "port": int(env["XRAY_PORT_WS"]),
                "protocol": "vless",
                "settings": {"clients": vless_users, "decryption": "none"},
                "streamSettings": {"network": "ws", "security": "none", "wsSettings": {"path": env["XRAY_WS_PATH"]}},
            },
            {
                "tag": "vless-grpc",
                "listen": "0.0.0.0",
                "port": int(env["XRAY_PORT_GRPC"]),
                "protocol": "vless",
                "settings": {"clients": vless_users, "decryption": "none"},
                "streamSettings": {
                    "network": "grpc",
                    "security": "none",
                    "grpcSettings": {"serviceName": env["XRAY_GRPC_SERVICE"]},
                },
            },
            {
                "tag": "vmess-ws",
                "listen": "0.0.0.0",
                "port": int(env["XRAY_PORT_VMESS"]),
                "protocol": "vmess",
                "settings": {"clients": vmess_users},
                "streamSettings": {"network": "ws", "wsSettings": {"path": env["XRAY_VMESS_WS_PATH"]}},
            },
        ],
        "outbounds": [{"protocol": "freedom", "tag": "direct"}, {"protocol": "blackhole", "tag": "block"}],
    }


def build_wg_server(users: dict[str, Any], env: dict[str, str], awg: bool = False) -> str:
    lines = [
        "[Interface]",
        f"PrivateKey = {env['WG_SERVER_PRIVATE_KEY']}",
        f"Address = {env['WG_SERVER_ADDRESS']}, {env['WG_SERVER_ADDRESS6']}",
        f"ListenPort = {env['WG_SERVER_PORT']}",
        f"PostUp = iptables -t nat -A POSTROUTING -o {env['SERVER_NIC']} -j MASQUERADE",
        f"PostDown = iptables -t nat -D POSTROUTING -o {env['SERVER_NIC']} -j MASQUERADE",
    ]
    if awg:
        lines.extend(
            [
                f"Jc = {env['AWG_JC']}",
                f"Jmin = {env['AWG_JMIN']}",
                f"Jmax = {env['AWG_JMAX']}",
                f"S1 = {env['AWG_S1']}",
                f"S2 = {env['AWG_S2']}",
                f"H1 = {env['AWG_H1']}",
                f"H2 = {env['AWG_H2']}",
                f"H3 = {env['AWG_H3']}",
                f"H4 = {env['AWG_H4']}",
            ]
        )

    for user in users.values():
        lines.extend(
            [
                "",
                "[Peer]",
                f"# {user['name']}",
                f"PublicKey = {user['wg_public_key']}",
                f"PresharedKey = {user['wg_preshared_key']}",
                f"AllowedIPs = {user['wg_ipv4'].split('/')[0]}/32, {user['wg_ipv6'].split('/')[0]}/128",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_3proxy(users: dict[str, Any], env: dict[str, str]) -> str:
    user_parts = [f"{user['proxy_username']}:CL:{user['proxy_password']}" for user in users.values()]
    if not user_parts:
        user_parts = ["placeholder:CL:placeholder"]
    return "\n".join(
        [
            "daemon",
            "nscache 65536",
            "auth strong",
            f"users {' '.join(user_parts)}",
            "",
            "allow *",
            f"proxy -n -a -p{env['HTTP_PROXY_PORT']}",
            "flush",
            "allow *",
            f"socks -p{env['SOCKS5_PROXY_PORT']}",
            "flush",
            "",
        ]
    )


def build_hysteria_server(users: dict[str, Any], env: dict[str, str]) -> str:
    lines = [
        f"listen: :{env['HY2_PORT']}",
        "",
        "tls:",
        f"  cert: {env['HY2_CERT_PATH']}",
        f"  key: {env['HY2_KEY_PATH']}",
        "",
        "auth:",
        "  type: userpass",
        "  userpass:",
    ]

    if users:
        for user in users.values():
            lines.append(f"    {user['hy2_username']}: {user['hy2_password']}")
    else:
        lines.append("    vpn-placeholder: disabled")

    lines.extend(
        [
            "",
            "obfs:",
            "  type: salamander",
            "  salamander:",
            f"    password: {env['HY2_OBFS_PASSWORD']}",
            "",
            "bandwidth:",
            f"  up: {env['HY2_UP_MBPS']} mbps",
            f"  down: {env['HY2_DOWN_MBPS']} mbps",
            "",
            "masquerade:",
            "  type: proxy",
            "  proxy:",
            f"    url: {env['HY2_MASQUERADE_URL']}",
            "    rewriteHost: true",
            "",
        ]
    )
    return "\n".join(lines)


def render_services() -> None:
    env = load_env()
    users = load_db()["users"]
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "xray_server.json").write_text(json.dumps(build_xray_server(users, env), indent=2) + "\n")
    (GENERATED_DIR / "hysteria_server.yaml").write_text(build_hysteria_server(users, env))
    (GENERATED_DIR / "wg_server.conf").write_text(build_wg_server(users, env, awg=False))
    (GENERATED_DIR / "awg_server.conf").write_text(build_wg_server(users, env, awg=True))
    (GENERATED_DIR / "3proxy.cfg").write_text(render_3proxy(users, env))


def user_add(name: str) -> None:
    ensure_layout()
    env = load_env()
    data = load_db()
    name = sanitize_name(name)
    if name in data["users"]:
        raise SystemExit(f"user '{name}' already exists")
    record = build_user_record(name, data["users"], env)
    data["users"][name] = record
    save_db(data)
    write_user_bundle(record, env)
    render_services()
    print(f"created user: {name}")


def user_del(name: str) -> None:
    data = load_db()
    name = sanitize_name(name)
    if name not in data["users"]:
        raise SystemExit(f"user '{name}' not found")
    del data["users"][name]
    save_db(data)
    shutil.rmtree(USERS_DIR / name, ignore_errors=True)
    render_services()
    print(f"deleted user: {name}")


def user_list() -> None:
    data = load_db()["users"]
    env = load_env()
    if not data:
        print("no users")
        return
    print(f"{'NAME':<16} {'CREATED':<20} {'PROTOCOLS':<40} SUBSCRIPTION")
    for name, user in sorted(data.items()):
        created = user["created"].replace("T", " ")[:19]
        protocols = "vless,xhttp,ws,grpc,vmess,hy2,wg,awg,proxy,mtproto"
        print(f"{name:<16} {created:<20} {protocols:<40} {subscription_url(env, name)}")


def user_info(name: str) -> None:
    name = sanitize_name(name)
    readme = USERS_DIR / name / "README.txt"
    if not readme.exists():
        raise SystemExit(f"user '{name}' not found")
    sys.stdout.write(readme.read_text())


def user_export(name: str, as_zip: bool) -> None:
    name = sanitize_name(name)
    user_dir = USERS_DIR / name
    if not user_dir.exists():
        raise SystemExit(f"user '{name}' not found")
    if not as_zip:
        print(user_dir)
        return
    archive_base = USERS_DIR / f"{name}"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=USERS_DIR, base_dir=name)
    print(archive_path)


def sub_info() -> None:
    data = load_db()["users"]
    env = load_env()
    print(f"Subscription endpoint: http://{env.get('SERVER_HOST') or env.get('SERVER_IP')}:{env['SUB_PORT']}/sub/<name>")
    if not data:
        print("No users yet.")
        return
    print("Users:")
    for name in sorted(data):
        print(f"  {name}: {subscription_url(env, name)}")


def status_summary() -> None:
    data = load_db()["users"]
    env = load_env()
    print(f"Users: {len(data)}")
    print(
        "Ports: "
        f"reality={env['XRAY_PORT_REALITY']} "
        f"xhttp={env['XRAY_PORT_XHTTP']} "
        f"ws={env['XRAY_PORT_WS']} "
        f"grpc={env['XRAY_PORT_GRPC']} "
        f"vmess={env['XRAY_PORT_VMESS']} "
        f"hy2={env['HY2_PORT']}/udp "
        f"http={env['HTTP_PROXY_PORT']} "
        f"socks5={env['SOCKS5_PROXY_PORT']} "
        f"sub={env['SUB_PORT']} "
        f"mtproto={env['MTPROTO_PORT']} "
        f"wg={env['WG_SERVER_PORT']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("render-services")
    sub.add_parser("status-summary")
    sub.add_parser("sub-info")

    p_add = sub.add_parser("user-add")
    p_add.add_argument("name")

    p_del = sub.add_parser("user-del")
    p_del.add_argument("name")

    sub.add_parser("user-list")

    p_info = sub.add_parser("user-info")
    p_info.add_argument("name")

    p_export = sub.add_parser("user-export")
    p_export.add_argument("name")
    p_export.add_argument("--zip", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "render-services":
        render_services()
    elif args.command == "status-summary":
        status_summary()
    elif args.command == "sub-info":
        sub_info()
    elif args.command == "user-add":
        user_add(args.name)
    elif args.command == "user-del":
        user_del(args.name)
    elif args.command == "user-list":
        user_list()
    elif args.command == "user-info":
        user_info(args.name)
    elif args.command == "user-export":
        user_export(args.name, args.zip)
    else:
        raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
