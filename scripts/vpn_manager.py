#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
USERS_DIR = ROOT / "users"
GENERATED_DIR = DATA_DIR / "generated"
USERS_DB_PATH = DATA_DIR / "users.json"
SERVER_ENV_PATH = DATA_DIR / "server.env"
USAGE_STATE_PATH = DATA_DIR / "usage_state.json"
USAGE_LOCK = Lock()

SERVICES = [
    ("xray.service", "Xray"),
    ("hysteria.service", "Hysteria2"),
    ("warp-svc.service", "Cloudflare WARP"),
    ("vpn-sub.service", "Subscription"),
    ("3proxy.service", "3proxy"),
    ("mtg.service", "MTProto"),
    ("wg-quick@wg0.service", "WireGuard"),
    ("awg-quick@awg0.service", "AmneziaWG"),
    ("vpn-bot.service", "Telegram bot"),
]

PROTOCOLS = "vless,reality,xhttp,ws,grpc,vmess,hy2,wg,awg,proxy,mtproto"

FILE_CLIENTS = {
    "xray": ("xray_client.json", "AmneziaVPN, v2rayN, Happ, Throne"),
    "singbox": ("singbox_client.json", "Streisand, Karing, NekoBox, v2RayTun"),
    "hy2": ("hy2_client.yaml", "Hysteria2 apps, sing-box, Happ"),
    "wg": ("wg.conf", "WireGuard"),
    "awg": ("awg.conf", "AmneziaWG, AmneziaVPN"),
    "proxy": ("proxy.txt", "HTTP/SOCKS5 apps, curl, browsers"),
    "mtproto": ("mtproto.txt", "Telegram"),
    "readme": ("README.txt", "Human-readable setup guide"),
    "uris": ("uris.txt", "Shareable URIs for manual import"),
    "subscription_url": ("subscription_url.txt", "One-click subscription URL"),
    "subscription_b64": ("subscription.b64", "Base64 subscription payload"),
    "qr_sub": ("qr_sub.png", "Subscription QR"),
    "qr_vless": ("qr_vless.png", "VLESS Reality QR"),
    "qr_wg": ("qr_wg.png", "WireGuard QR"),
}

COLOR = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}

os.umask(0o077)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def supports_color(stream: Any) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR")


def paint(text: str, *styles: str, enabled: bool | None = None) -> str:
    if enabled is None:
        enabled = supports_color(sys.stdout)
    if not enabled:
        return text
    prefix = "".join(COLOR[style] for style in styles if style in COLOR)
    return f"{prefix}{text}{COLOR['reset']}"


def payload(kind: str, data: Any, *, message: str | None = None) -> dict[str, Any]:
    result = {"ok": True, "kind": kind, "data": data}
    if message:
        result["message"] = message
    return result


def print_json(kind: str, data: Any, *, message: str | None = None) -> None:
    print(json.dumps(payload(kind, data, message=message), indent=2, ensure_ascii=False))


def ensure_layout() -> None:
    for path in (DATA_DIR, USERS_DIR, GENERATED_DIR):
        path.mkdir(parents=True, exist_ok=True)
    if not USERS_DB_PATH.exists():
        USERS_DB_PATH.write_text(json.dumps({"users": {}}, indent=2) + "\n")
    if not SERVER_ENV_PATH.exists():
        raise SystemExit("missing data/server.env, run vpn install or create the file")


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


def load_usage_state() -> dict[str, Any]:
    ensure_layout()
    if not USAGE_STATE_PATH.exists():
        return {"updated_at": None, "users": {}}
    try:
        with USAGE_STATE_PATH.open() as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"updated_at": None, "users": {}}
    data.setdefault("users", {})
    return data


def save_usage_state(data: dict[str, Any]) -> None:
    USAGE_STATE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def int_or_zero(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def optional_int(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    amount = float(max(value, 0))
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{value} B"


def parse_meminfo() -> dict[str, int]:
    path = Path("/proc/meminfo")
    result: dict[str, int] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        pieces = raw_value.strip().split()
        if not pieces:
            continue
        result[key] = int_or_zero(pieces[0]) * 1024
    return result


def parse_netdev() -> list[dict[str, Any]]:
    path = Path("/proc/net/dev")
    if not path.exists():
        return []
    interfaces: list[dict[str, Any]] = []
    for line in path.read_text().splitlines()[2:]:
        if ":" not in line:
            continue
        name, payload_text = line.split(":", 1)
        fields = payload_text.split()
        if len(fields) < 16:
            continue
        interfaces.append(
            {
                "name": name.strip(),
                "rx_bytes": int_or_zero(fields[0]),
                "rx_packets": int_or_zero(fields[1]),
                "tx_bytes": int_or_zero(fields[8]),
                "tx_packets": int_or_zero(fields[9]),
            }
        )
    return interfaces


def server_load_payload() -> dict[str, Any]:
    load1 = load5 = load15 = 0.0
    if hasattr(os, "getloadavg"):
        try:
            load1, load5, load15 = os.getloadavg()
        except OSError:
            pass
    memory = parse_meminfo()
    total_memory = int_or_zero(memory.get("MemTotal"))
    available_memory = int_or_zero(memory.get("MemAvailable") or memory.get("MemFree"))
    used_memory = max(total_memory - available_memory, 0)
    disk = shutil.disk_usage(ROOT)
    uptime_seconds = 0.0
    uptime_path = Path("/proc/uptime")
    if uptime_path.exists():
        try:
            uptime_seconds = float(uptime_path.read_text().split()[0])
        except (ValueError, OSError, IndexError):
            uptime_seconds = 0.0
    interfaces = parse_netdev()
    rx_total = sum(item["rx_bytes"] for item in interfaces)
    tx_total = sum(item["tx_bytes"] for item in interfaces)
    return {
        "cpu": {
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
            "cores": os.cpu_count() or 0,
        },
        "memory": {
            "total_bytes": total_memory,
            "used_bytes": used_memory,
            "available_bytes": available_memory,
            "used_percent": round((used_memory / total_memory) * 100, 2) if total_memory else 0.0,
        },
        "disk": {
            "path": str(ROOT),
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "used_percent": round((disk.used / disk.total) * 100, 2) if disk.total else 0.0,
        },
        "network": {
            "rx_bytes": rx_total,
            "tx_bytes": tx_total,
            "interfaces": interfaces,
        },
        "uptime_seconds": round(uptime_seconds, 2),
    }


def parse_xray_stats_output(raw: str) -> dict[str, dict[str, int]]:
    def apply_record(target: dict[str, dict[str, int]], name: str, value: Any) -> None:
        parts = name.split(">>>")
        if len(parts) != 4 or parts[0] != "user" or parts[2] != "traffic":
            return
        direction = parts[3]
        if direction not in {"uplink", "downlink"}:
            return
        email = parts[1]
        bucket = target.setdefault(email, {"uplink": 0, "downlink": 0})
        bucket[direction] += int_or_zero(value)

    if not raw.strip():
        return {}
    usage: dict[str, dict[str, int]] = {}
    try:
        payload_data = json.loads(raw)
    except json.JSONDecodeError:
        payload_data = None
    if isinstance(payload_data, dict):
        for item in payload_data.get("stat", []):
            apply_record(usage, str(item.get("name", "")), item.get("value"))
        if usage:
            return usage

    current_name = ""
    for line in raw.splitlines():
        stripped = line.strip()
        name_match = re.match(r'^name:\s+"([^"]+)"$', stripped)
        if name_match:
            current_name = name_match.group(1)
            continue
        value_match = re.match(r'^value:\s+"?([0-9]+)"?$', stripped)
        if value_match and current_name:
            apply_record(usage, current_name, value_match.group(1))
            current_name = ""
    return usage


def query_xray_user_stats(env: dict[str, str]) -> dict[str, dict[str, int]] | None:
    if not command_exists("xray"):
        return None
    server = (env.get("XRAY_API_LISTEN") or "").strip()
    if not server:
        return None
    proc = run_command("xray", "api", "statsquery", f"--server={server}", check=False)
    if proc.returncode != 0:
        return None
    return parse_xray_stats_output(proc.stdout)


def build_usage_payload(data: dict[str, Any], usage_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    state_users = usage_state.get("users", {})
    usage: dict[str, dict[str, Any]] = {}
    for name, user in sorted(data["users"].items()):
        entry = state_users.get(user.get("email", ""), {})
        uplink = int_or_zero(entry.get("total_uplink"))
        downlink = int_or_zero(entry.get("total_downlink"))
        total = uplink + downlink
        quota_bytes = optional_int(user.get("quota_bytes"))
        usage[name] = {
            "name": name,
            "email": user.get("email", ""),
            "uplink_bytes": uplink,
            "downlink_bytes": downlink,
            "total_bytes": total,
            "quota_bytes": quota_bytes,
            "quota_remaining_bytes": max(quota_bytes - total, 0) if quota_bytes else None,
            "usage_percent": round((total / quota_bytes) * 100, 2) if quota_bytes else None,
            "updated_at": entry.get("updated_at") or usage_state.get("updated_at"),
            "source": "xray",
            "state": "suspended" if user.get("suspended") else "active",
        }
    return usage


def apply_quota_enforcement(data: dict[str, Any], usage: dict[str, dict[str, Any]]) -> bool:
    changed = False
    for name, user in data.get("users", {}).items():
        quota_bytes = optional_int(user.get("quota_bytes"))
        if not quota_bytes or user.get("quota_override"):
            continue
        usage_item = usage.get(name) or usage.get(user.get("email", ""))
        total_bytes = int_or_zero((usage_item or {}).get("total_bytes"))
        if total_bytes >= quota_bytes and not user.get("suspended"):
            user["suspended"] = True
            user["suspension_reason"] = "quota"
            user["suspended_at"] = now_utc()
            changed = True
    return changed


def usage_snapshot(*, refresh: bool = True) -> dict[str, dict[str, Any]]:
    data = load_db()
    env = load_env()
    with USAGE_LOCK:
        state = load_usage_state()
        current_stats = query_xray_user_stats(env) if refresh else None
        if current_stats is not None:
            tracked_users = state.setdefault("users", {})
            emails = {user.get("email", ""): name for name, user in data["users"].items() if user.get("email")}
            for email in list(tracked_users):
                if email not in emails:
                    del tracked_users[email]
            for email, name in emails.items():
                current = current_stats.get(email, {})
                previous = tracked_users.get(email, {})
                current_up = int_or_zero(current.get("uplink"))
                current_down = int_or_zero(current.get("downlink"))
                previous_up = int_or_zero(previous.get("raw_uplink"))
                previous_down = int_or_zero(previous.get("raw_downlink"))
                delta_up = current_up - previous_up if current_up >= previous_up else current_up
                delta_down = current_down - previous_down if current_down >= previous_down else current_down
                tracked_users[email] = {
                    "name": name,
                    "raw_uplink": current_up,
                    "raw_downlink": current_down,
                    "total_uplink": int_or_zero(previous.get("total_uplink")) + delta_up,
                    "total_downlink": int_or_zero(previous.get("total_downlink")) + delta_down,
                    "updated_at": now_utc(),
                }
            state["updated_at"] = now_utc()
            save_usage_state(state)
        usage = build_usage_payload(data, state)
        changed = apply_quota_enforcement(data, usage)
        if changed:
            save_db(data)
            usage = build_usage_payload(data, state)
    if changed:
        render_services()
        sync_live_configs(env)
    return usage


def user_usage_payload(name: str | None = None, *, refresh: bool = True) -> Any:
    usage = usage_snapshot(refresh=refresh)
    if name is None:
        return {item: usage[item] for item in sorted(usage)}
    safe_name = sanitize_name(name)
    if safe_name not in usage:
        raise SystemExit(f"user '{safe_name}' not found")
    return usage[safe_name]


def clear_quota_suspension(user: dict[str, Any]) -> bool:
    if user.get("suspension_reason") != "quota":
        return False
    user["suspended"] = False
    user.pop("suspension_reason", None)
    user.pop("suspended_at", None)
    return True


def active_users(users: dict[str, Any]) -> dict[str, Any]:
    return {name: user for name, user in users.items() if not user.get("suspended")}


def sanitize_name(name: str) -> str:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip("-_")
    if not safe:
        raise SystemExit("invalid user name")
    return safe


def random_b64(length: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(length)).decode()


def run_command(
    *cmd: str,
    input_text: str | None = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        input=input_text,
        text=True,
        check=check,
        capture_output=capture_output,
    )


def command_output(*cmd: str, input_text: str | None = None) -> str:
    return run_command(*cmd, input_text=input_text).stdout.strip()


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def require_root() -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise SystemExit("root privileges are required")


def service_state(service: str) -> str:
    if not command_exists("systemctl"):
        return "systemctl-unavailable"
    proc = run_command("systemctl", "is-active", service, check=False)
    return (proc.stdout.strip() or proc.stderr.strip() or "unknown").strip()


def service_unit_exists(service: str) -> bool:
    if not command_exists("systemctl"):
        return False
    proc = run_command("systemctl", "list-unit-files", service, check=False)
    return service in proc.stdout


def restart_service_if_present(service: str) -> None:
    if service_unit_exists(service):
        run_command("systemctl", "restart", service, check=False)


def copy_if_possible(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except PermissionError:
        return
    except OSError:
        return


def sync_live_configs(env: dict[str, str]) -> None:
    xray_dst = Path(env.get("XRAY_CONFIG_PATH", ""))
    if xray_dst:
        copy_if_possible(GENERATED_DIR / "xray_server.json", xray_dst)
        if command_exists("xray") and xray_dst.exists():
            proc = run_command("xray", "run", "-test", "-config", str(xray_dst), check=False)
            if proc.returncode != 0:
                raise SystemExit("xray config validation failed")
        restart_service_if_present("xray.service")

    hy2_dst = Path(env.get("HY2_CONFIG_PATH", ""))
    if hy2_dst:
        copy_if_possible(GENERATED_DIR / "hysteria_server.yaml", hy2_dst)
        restart_service_if_present("hysteria.service")

    proxy_dst = Path(env.get("THREEPROXY_CONFIG_PATH", ""))
    if proxy_dst:
        copy_if_possible(GENERATED_DIR / "3proxy.cfg", proxy_dst)
        restart_service_if_present("3proxy.service")

    wg_dst = Path(env.get("WG_SERVER_CONFIG_PATH", ""))
    if wg_dst:
        copy_if_possible(GENERATED_DIR / "wg_server.conf", wg_dst)
        restart_service_if_present("wg-quick@wg0.service")

    awg_dst = Path(env.get("AWG_SERVER_CONFIG_PATH", ""))
    if awg_dst:
        copy_if_possible(GENERATED_DIR / "awg_server.conf", awg_dst)
        restart_service_if_present("awg-quick@awg0.service")


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
    return {
        "name": name,
        "created": now_utc(),
        "uuid": str(uuid.uuid4()),
        "email": f"{name}@vpn.local",
        "proxy_username": name,
        "proxy_password": secrets.token_urlsafe(12),
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
        "obfs=salamander",
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
        "dns": {
            "strategy": "prefer_ipv4",
            "servers": [
                {"type": "local", "tag": "local-dns"},
                {
                    "type": "https",
                    "tag": "remote-dns",
                    "server": "1.1.1.1",
                    "server_port": 443,
                    "path": "/dns-query",
                    "tls": {"enabled": True, "server_name": "cloudflare-dns.com"},
                },
            ],
            "rules": [
                {"domain_suffix": ["local"], "server": "local-dns"},
                {"query_type": ["A", "AAAA"], "server": "remote-dns"},
            ],
            "final": "remote-dns",
            "independent_cache": True,
        },
        "inbounds": [{"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2080}],
        "outbounds": outbounds,
        "route": {
            "auto_detect_interface": True,
            "final": "select",
            "rules": [
                {"domain_suffix": ["local"], "outbound": "direct"},
                {"ip_is_private": True, "outbound": "direct"},
            ],
        },
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


def is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def bundle_file_index(user_dir: Path) -> dict[str, Path]:
    return {key: user_dir / name for key, (name, _clients) in FILE_CLIENTS.items()}


def build_readme(user: dict[str, Any], env: dict[str, str], uris: list[str]) -> str:
    lines = [
        f"=== VPN Configs for: {user['name']} ===",
        f"Generated: {today_local()}",
        "",
        "[SUBSCRIPTION URL - recommended, imports everything at once]",
        subscription_url(env, user["name"]),
        "",
        "[FILES BY CLIENT / APP]",
        "xray_client.json -> AmneziaVPN, v2rayN, Happ, Throne",
        "singbox_client.json -> Streisand, Karing, NekoBox, v2RayTun",
        "hy2_client.yaml -> Hysteria2 apps, sing-box, Happ",
        "wg.conf -> WireGuard",
        "awg.conf -> AmneziaWG, AmneziaVPN",
        "proxy.txt -> HTTP/SOCKS5 apps, curl, browsers",
        "mtproto.txt -> Telegram",
        "",
        "[QUICK IMPORT]",
        "Desktop: use the subscription URL in v2rayN / Throne / Karing / Happ",
        "Android: use the subscription URL in v2rayNG / NekoBox / v2Box / v2RayTun",
        "iPhone/iPad: use the subscription URL in Streisand / Shadowrocket / Karing / V2Box / v2RayTun / Happ",
        "AmneziaVPN: import xray_client.json, awg.conf or wg.conf",
        "Hysteria2-compatible apps: import the hysteria2:// URI from uris.txt or use hy2_client.yaml",
        "Telegram: open a link from mtproto.txt",
        "HTTP/SOCKS5 proxy: use proxy.txt",
        "",
        "[ALL SHAREABLE URIS]",
        *uris,
        "",
    ]
    return "\n".join(lines)


def maybe_qr_png(payload_text: str, output: Path) -> None:
    try:
        run_command("qrencode", "-o", str(output), payload_text)
    except Exception:
        pass


def render_terminal_qrs(name: str) -> None:
    user_dir = USERS_DIR / name
    if not user_dir.is_dir() or not command_exists("qrencode") or not supports_color(sys.stdout):
        return
    print()
    print(paint("[QR] Subscription", "bold", "cyan"))
    run_command("qrencode", "-t", "ANSIUTF8", check=False, capture_output=False, input_text=(user_dir / "subscription_url.txt").read_text())
    print()
    print(paint("[QR] VLESS Reality", "bold", "cyan"))
    run_command("qrencode", "-t", "ANSIUTF8", check=False, capture_output=False, input_text=(user_dir / "uris.txt").read_text().splitlines()[0] + "\n")
    print()
    print(paint("[QR] WireGuard", "bold", "cyan"))
    run_command("qrencode", "-t", "ANSIUTF8", check=False, capture_output=False, input_text=(user_dir / "wg.conf").read_text())


def write_user_bundle(user: dict[str, Any], env: dict[str, str]) -> None:
    user_dir = USERS_DIR / user["name"]
    user_dir.mkdir(parents=True, exist_ok=True)
    uris = build_uris(user, env)
    raw_uris = "\n".join(uris) + "\n"
    sub_b64 = base64.b64encode(raw_uris.encode()).decode()
    sub_url = subscription_url(env, user["name"])
    files = bundle_file_index(user_dir)

    files["uris"].write_text(raw_uris)
    files["subscription_b64"].write_text(sub_b64 + "\n")
    files["subscription_url"].write_text(sub_url + "\n")
    files["xray"].write_text(json.dumps(build_xray_client(user, env), indent=2) + "\n")
    files["singbox"].write_text(json.dumps(build_singbox_client(user, env), indent=2) + "\n")
    files["hy2"].write_text(build_hy2_client(user, env))
    files["wg"].write_text(build_wg_client(user, env))
    files["awg"].write_text(build_awg_client(user, env))
    files["proxy"].write_text(build_proxy_txt(user, env))
    files["mtproto"].write_text(build_mtproto_txt(env))
    files["readme"].write_text(build_readme(user, env, uris))

    maybe_qr_png(uris[0], files["qr_vless"])
    maybe_qr_png(files["wg"].read_text(), files["qr_wg"])
    maybe_qr_png(sub_url, files["qr_sub"])


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
    outbounds: list[dict[str, Any]] = [
        {"protocol": "freedom", "tag": "direct"},
        {"protocol": "blackhole", "tag": "block"},
    ]
    routing_rules: list[dict[str, Any]] = []

    if is_truthy(env.get("XRAY_WARP_ENABLE")):
        outbounds.append(
            {
                "protocol": "socks",
                "tag": "warp",
                "settings": {
                    "servers": [
                        {
                            "address": "127.0.0.1",
                            "port": int(env.get("XRAY_WARP_PORT", "40000")),
                        }
                    ]
                },
            }
        )
        warp_domains = parse_csv_env(env.get("XRAY_WARP_DOMAINS"))
        if warp_domains:
            routing_rules.append(
                {
                    "type": "field",
                    "domain": warp_domains,
                    "outboundTag": "warp",
                }
            )
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
        "routing": {
            "domainStrategy": "AsIs",
            "rules": routing_rules,
        },
        "outbounds": outbounds,
    }


def build_wg_server(users: dict[str, Any], env: dict[str, str], *, awg: bool = False) -> str:
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
    users = active_users(load_db()["users"])
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "xray_server.json").write_text(json.dumps(build_xray_server(users, env), indent=2) + "\n")
    (GENERATED_DIR / "hysteria_server.yaml").write_text(build_hysteria_server(users, env))
    (GENERATED_DIR / "wg_server.conf").write_text(build_wg_server(users, env, awg=False))
    (GENERATED_DIR / "awg_server.conf").write_text(build_wg_server(users, env, awg=True))
    (GENERATED_DIR / "3proxy.cfg").write_text(render_3proxy(users, env))


def user_summary(user: dict[str, Any], env: dict[str, str], usage: dict[str, Any] | None = None) -> dict[str, Any]:
    usage_item = usage or {}
    total_bytes = int_or_zero(usage_item.get("total_bytes"))
    quota_bytes = optional_int(user.get("quota_bytes"))
    return {
        "name": user["name"],
        "created": user["created"].replace("T", " ")[:19],
        "subscription_url": subscription_url(env, user["name"]),
        "protocols": PROTOCOLS,
        "state": "suspended" if user.get("suspended") else "active",
        "quota_bytes": quota_bytes,
        "quota_human": format_bytes(quota_bytes) if quota_bytes else "unlimited",
        "used_bytes": total_bytes,
        "used_human": format_bytes(total_bytes),
        "usage_percent": usage_item.get("usage_percent"),
        "quota_remaining_bytes": usage_item.get("quota_remaining_bytes"),
        "quota_remaining_human": (
            format_bytes(int_or_zero(usage_item["quota_remaining_bytes"]))
            if usage_item.get("quota_remaining_bytes") is not None
            else "unlimited"
        ),
        "updated_at": usage_item.get("updated_at"),
    }


def user_file_payload(name: str) -> dict[str, str]:
    name = sanitize_name(name)
    user_dir = USERS_DIR / name
    if not user_dir.is_dir():
        raise SystemExit(f"user '{name}' not found")
    files = bundle_file_index(user_dir)
    return {
        "xray": str(files["xray"]),
        "singbox": str(files["singbox"]),
        "hy2": str(files["hy2"]),
        "wg": str(files["wg"]),
        "awg": str(files["awg"]),
        "proxy": str(files["proxy"]),
        "mtproto": str(files["mtproto"]),
        "readme": str(files["readme"]),
        "subscription_url": str(files["subscription_url"]),
        "uris": str(files["uris"]),
    }


def user_info_payload(name: str) -> dict[str, Any]:
    data = load_db()["users"]
    env = load_env()
    usage = user_usage_payload(refresh=True)
    name = sanitize_name(name)
    if name not in data:
        raise SystemExit(f"user '{name}' not found")
    files = user_file_payload(name)
    user_dir = USERS_DIR / name
    return {
        **user_summary(data[name], env, usage.get(name)),
        "usage": usage.get(name, {}),
        "files": files,
        "shareable_uris": (user_dir / "uris.txt").read_text().splitlines(),
        "readme": (user_dir / "README.txt").read_text(),
    }


def user_export_payload(name: str, as_zip: bool) -> dict[str, Any]:
    name = sanitize_name(name)
    user_dir = USERS_DIR / name
    if not user_dir.exists():
        raise SystemExit(f"user '{name}' not found")
    archive_path = None
    if as_zip:
        archive_path = shutil.make_archive(str(USERS_DIR / name), "zip", root_dir=USERS_DIR, base_dir=name)
    return {
        "name": name,
        "user_dir": str(user_dir),
        "archive_path": archive_path,
        "files": user_file_payload(name),
    }


def user_add(name: str) -> dict[str, Any]:
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
    sync_live_configs(env)
    return user_info_payload(name)


def user_del(name: str) -> None:
    env = load_env()
    data = load_db()
    name = sanitize_name(name)
    if name not in data["users"]:
        raise SystemExit(f"user '{name}' not found")
    user = data["users"][name]
    del data["users"][name]
    save_db(data)
    with USAGE_LOCK:
        usage_state = load_usage_state()
        usage_state.get("users", {}).pop(user.get("email", ""), None)
        save_usage_state(usage_state)
    shutil.rmtree(USERS_DIR / name, ignore_errors=True)
    render_services()
    sync_live_configs(env)


def set_user_quota(name: str, quota_bytes: int | None) -> dict[str, Any]:
    env = load_env()
    data = load_db()
    safe_name = sanitize_name(name)
    if safe_name not in data["users"]:
        raise SystemExit(f"user '{safe_name}' not found")
    user = data["users"][safe_name]
    needs_render = False
    user.pop("quota_override", None)
    if quota_bytes is None:
        user.pop("quota_bytes", None)
        needs_render = clear_quota_suspension(user)
    else:
        user["quota_bytes"] = quota_bytes
    save_db(data)
    if needs_render:
        render_services()
        sync_live_configs(env)
    usage_snapshot(refresh=True)
    return user_info_payload(safe_name)


def set_user_suspension(name: str, suspended: bool, *, reason: str) -> dict[str, Any]:
    env = load_env()
    data = load_db()
    safe_name = sanitize_name(name)
    if safe_name not in data["users"]:
        raise SystemExit(f"user '{safe_name}' not found")
    user = data["users"][safe_name]
    if suspended:
        user["suspended"] = True
        user["suspension_reason"] = reason
        user["suspended_at"] = now_utc()
        user.pop("quota_override", None)
    else:
        user["suspended"] = False
        if user.get("suspension_reason") == "quota":
            user["quota_override"] = True
        else:
            user.pop("quota_override", None)
        user.pop("suspension_reason", None)
        user.pop("suspended_at", None)
    save_db(data)
    render_services()
    sync_live_configs(env)
    return user_info_payload(safe_name)


def reset_user_usage(name: str) -> dict[str, Any]:
    data = load_db()
    env = load_env()
    safe_name = sanitize_name(name)
    if safe_name not in data["users"]:
        raise SystemExit(f"user '{safe_name}' not found")
    user = data["users"][safe_name]
    current_stats = query_xray_user_stats(env) or {}
    current = current_stats.get(user.get("email", ""), {})
    with USAGE_LOCK:
        usage_state = load_usage_state()
        usage_state.setdefault("users", {})[user["email"]] = {
            "name": safe_name,
            "raw_uplink": int_or_zero(current.get("uplink")),
            "raw_downlink": int_or_zero(current.get("downlink")),
            "total_uplink": 0,
            "total_downlink": 0,
            "updated_at": now_utc(),
        }
        usage_state["updated_at"] = now_utc()
        save_usage_state(usage_state)
    if clear_quota_suspension(user):
        user.pop("quota_override", None)
        save_db(data)
        render_services()
        sync_live_configs(env)
    return user_info_payload(safe_name)


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    head = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    body = ["  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in rows]
    return "\n".join([head, *body])


def color_service_state(state: str) -> str:
    if state == "active":
        return paint(state, "green", "bold")
    if state in {"inactive", "activating", "deactivating"}:
        return paint(state, "yellow")
    if state in {"failed", "unknown"}:
        return paint(state, "red", "bold")
    return paint(state, "dim")


def status_payload() -> dict[str, Any]:
    data = load_db()["users"]
    env = load_env()
    usage = user_usage_payload(refresh=True)
    services = [
        {"unit": unit, "name": label, "state": service_state(unit)}
        for unit, label in SERVICES
    ]
    ports = {
        "reality": env["XRAY_PORT_REALITY"],
        "xhttp": env["XRAY_PORT_XHTTP"],
        "ws": env["XRAY_PORT_WS"],
        "grpc": env["XRAY_PORT_GRPC"],
        "vmess": env["XRAY_PORT_VMESS"],
        "hy2_udp": env["HY2_PORT"],
        "http_proxy": env["HTTP_PROXY_PORT"],
        "socks5_proxy": env["SOCKS5_PROXY_PORT"],
        "subscription": env["SUB_PORT"],
        "mtproto": env["MTPROTO_PORT"],
        "wireguard": env["WG_SERVER_PORT"],
    }
    return {
        "users": len(data),
        "active_users": sum(1 for user in data.values() if not user.get("suspended")),
        "suspended_users": sum(1 for user in data.values() if user.get("suspended")),
        "server_host": env.get("SERVER_HOST") or env.get("SERVER_IP"),
        "ports": ports,
        "services": services,
        "load": server_load_payload(),
        "top_usage": sorted(usage.values(), key=lambda item: item["total_bytes"], reverse=True)[:5],
    }


def print_status_summary(*, legacy: bool = False) -> None:
    data = status_payload()
    if legacy:
        ports = data["ports"]
        print(f"Users: {data['users']}")
        print(
            "Ports: "
            f"reality={ports['reality']} "
            f"xhttp={ports['xhttp']} "
            f"ws={ports['ws']} "
            f"grpc={ports['grpc']} "
            f"vmess={ports['vmess']} "
            f"hy2={ports['hy2_udp']}/udp "
            f"http={ports['http_proxy']} "
            f"socks5={ports['socks5_proxy']} "
            f"sub={ports['subscription']} "
            f"mtproto={ports['mtproto']} "
            f"wg={ports['wireguard']}"
        )
        return

    print(paint("Status", "bold", "cyan"))
    print(
        f"Users: {paint(str(data['users']), 'bold')} "
        f"(active {data['active_users']}, suspended {data['suspended_users']})"
    )
    port_rows = [[name, str(value)] for name, value in data["ports"].items()]
    print()
    print(paint("Ports", "bold"))
    print(format_table(["NAME", "VALUE"], port_rows))
    print()
    load = data["load"]
    load_rows = [
        ["CPU load", f"{load['cpu']['load1']} / {load['cpu']['load5']} / {load['cpu']['load15']}"],
        ["Memory", f"{format_bytes(load['memory']['used_bytes'])} / {format_bytes(load['memory']['total_bytes'])} ({load['memory']['used_percent']}%)"],
        ["Disk", f"{format_bytes(load['disk']['used_bytes'])} / {format_bytes(load['disk']['total_bytes'])} ({load['disk']['used_percent']}%)"],
        ["Network RX", format_bytes(load["network"]["rx_bytes"])],
        ["Network TX", format_bytes(load["network"]["tx_bytes"])],
    ]
    print(paint("Server Load", "bold"))
    print(format_table(["METRIC", "VALUE"], load_rows))
    print()
    print(paint("Services", "bold"))
    service_rows = [[item["name"], item["unit"], color_service_state(item["state"])] for item in data["services"]]
    print(format_table(["SERVICE", "UNIT", "STATE"], service_rows))
    if data["top_usage"]:
        print()
        print(paint("Top Traffic", "bold"))
        traffic_rows = [
            [
                item["name"],
                format_bytes(item["total_bytes"]),
                item.get("state", "active"),
                format_bytes(item["quota_bytes"]) if item.get("quota_bytes") else "unlimited",
            ]
            for item in data["top_usage"]
        ]
        print(format_table(["USER", "USED", "STATE", "QUOTA"], traffic_rows))


def sub_payload() -> dict[str, Any]:
    data = load_db()["users"]
    env = load_env()
    host = env.get("SERVER_HOST") or env.get("SERVER_IP") or "127.0.0.1"
    base = f"http://{host}:{env['SUB_PORT']}"
    return {
        "base_url": base,
        "subscription_template": f"{base}/sub/<name>",
        "raw_subscription_template": f"{base}/sub/<name>/raw",
        "users": [{"name": name, "subscription_url": subscription_url(env, name)} for name in sorted(data)],
    }


def print_sub_summary(*, legacy: bool = False) -> None:
    data = sub_payload()
    if legacy:
        print(f"Subscription endpoint: {data['subscription_template']}")
        if not data["users"]:
            print("No users yet.")
            return
        print("Users:")
        for user in data["users"]:
            print(f"  {user['name']}: {user['subscription_url']}")
        return

    print(paint("Subscriptions", "bold", "cyan"))
    print(f"Base64 endpoint: {data['subscription_template']}")
    print(f"Raw endpoint:    {data['raw_subscription_template']}")
    if not data["users"]:
        print()
        print("No users yet.")
        return
    print()
    rows = [[item["name"], item["subscription_url"]] for item in data["users"]]
    print(format_table(["USER", "URL"], rows))


def print_user_list() -> None:
    data = load_db()["users"]
    env = load_env()
    usage = user_usage_payload(refresh=True)
    if not data:
        print("no users")
        return
    rows = [
        [
            summary["name"],
            summary["created"],
            summary["state"],
            summary["used_human"],
            summary["quota_human"],
            summary["protocols"],
            summary["subscription_url"],
        ]
        for summary in (user_summary(user, env, usage.get(_name)) for _name, user in sorted(data.items()))
    ]
    print(format_table(["NAME", "CREATED", "STATE", "USED", "QUOTA", "PROTOCOLS", "SUBSCRIPTION"], rows))


def print_user_config(name: str) -> None:
    files = user_file_payload(name)
    rows = [[key.upper(), value] for key, value in files.items()]
    print(format_table(["FILE", "PATH"], rows))


def print_user_info(name: str, *, show_qr: bool) -> None:
    name = sanitize_name(name)
    readme = USERS_DIR / name / "README.txt"
    if not readme.exists():
        raise SystemExit(f"user '{name}' not found")
    sys.stdout.write(readme.read_text())
    if show_qr:
        render_terminal_qrs(name)


def print_user_usage(name: str | None = None) -> None:
    if name:
        item = user_usage_payload(name, refresh=True)
        rows = [
            ["User", item["name"]],
            ["State", item["state"]],
            ["Uplink", format_bytes(item["uplink_bytes"])],
            ["Downlink", format_bytes(item["downlink_bytes"])],
            ["Total", format_bytes(item["total_bytes"])],
            ["Quota", format_bytes(item["quota_bytes"]) if item.get("quota_bytes") else "unlimited"],
            ["Remaining", format_bytes(item["quota_remaining_bytes"]) if item.get("quota_remaining_bytes") is not None else "unlimited"],
            ["Updated", item.get("updated_at") or "n/a"],
        ]
        print(format_table(["FIELD", "VALUE"], rows))
        return

    rows = [
        [
            item["name"],
            item["state"],
            format_bytes(item["total_bytes"]),
            format_bytes(item["quota_bytes"]) if item.get("quota_bytes") else "unlimited",
            item.get("updated_at") or "n/a",
        ]
        for item in user_usage_payload(refresh=True).values()
    ]
    if not rows:
        print("no users")
        return
    print(format_table(["USER", "STATE", "USED", "QUOTA", "UPDATED"], rows))


def fetch_logs(service: str) -> list[str]:
    if not command_exists("journalctl"):
        raise SystemExit("journalctl is not available on this system")
    proc = run_command("journalctl", "-u", service, "-n", "50", "--no-pager", check=False)
    return proc.stdout.rstrip().splitlines()


def install_stack() -> None:
    run_command("bash", str(ROOT / "install.sh"), capture_output=False)


def update_stack() -> None:
    for script in ("install_xray.sh", "install_hysteria.sh", "install_mtproto.sh"):
        run_command("bash", str(ROOT / "scripts" / script), "--upgrade", capture_output=False)


def uninstall_stack(*, yes: bool) -> None:
    require_root()
    if not yes:
        answer = input("Remove services and generated configs? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("aborted")
            return

    if command_exists("systemctl"):
        run_command(
            "systemctl",
            "disable",
            "--now",
            "vpn-bot.service",
            "vpn-sub.service",
            "mtg.service",
            "3proxy.service",
            "xray.service",
            "hysteria.service",
            "wg-quick@wg0.service",
            "awg-quick@awg0.service",
            check=False,
        )
    for path in (
        "/usr/local/bin/vpn",
        "/etc/systemd/system/vpn-sub.service",
        "/etc/systemd/system/vpn-bot.service",
        "/etc/systemd/system/hysteria.service",
        "/etc/systemd/system/3proxy.service",
    ):
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
    if command_exists("systemctl"):
        run_command("systemctl", "daemon-reload", check=False)
    print(f"Stack services removed. Project files remain in: {ROOT}")


def detect_completion_shell(value: str | None) -> str:
    if value:
        return value
    shell = Path(os.environ.get("SHELL", "bash")).name
    return "zsh" if shell == "zsh" else "bash"


def completion_script(shell_name: str) -> str:
    bash_script = r'''
# vpn commands: install, user add, user del, user list, user config, user info, user export, user usage, user limit, user suspend, user resume, user reset-usage, sub, panel, status, logs, update, uninstall, completion
_vpn_user_names() {
  vpn user list --json 2>/dev/null | python3 -c 'import json,sys
try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
items = data.get("data", [])
print(" ".join(item.get("name", "") for item in items if item.get("name")))' 
}

_vpn_complete() {
  local cur prev
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"

  if [[ ${COMP_CWORD} -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "install user sub panel status logs update uninstall completion" -- "${cur}") )
    return
  fi

  case "${COMP_WORDS[1]}" in
    user)
      if [[ ${COMP_CWORD} -eq 2 ]]; then
        COMPREPLY=( $(compgen -W "add del list config info export usage limit suspend resume reset-usage" -- "${cur}") )
        return
      fi
      case "${COMP_WORDS[2]}" in
        del|config|info|export|usage|limit|suspend|resume|reset-usage)
          COMPREPLY=( $(compgen -W "$(_vpn_user_names) --json --zip --no-qr" -- "${cur}") )
          return
          ;;
        add)
          COMPREPLY=( $(compgen -W "--json --no-qr" -- "${cur}") )
          return
          ;;
        list)
          COMPREPLY=( $(compgen -W "--json" -- "${cur}") )
          return
          ;;
      esac
      ;;
    sub|status)
      COMPREPLY=( $(compgen -W "--json" -- "${cur}") )
      return
      ;;
    logs)
      COMPREPLY=( $(compgen -W "xray.service hysteria.service vpn-sub.service 3proxy.service mtg.service wg-quick@wg0.service awg-quick@awg0.service vpn-bot.service --json" -- "${cur}") )
      return
      ;;
    uninstall)
      COMPREPLY=( $(compgen -W "--yes" -- "${cur}") )
      return
      ;;
    completion)
      COMPREPLY=( $(compgen -W "bash zsh" -- "${cur}") )
      return
      ;;
  esac
}

complete -F _vpn_complete vpn
'''.strip()
    if shell_name == "bash":
        return bash_script
    return "#compdef vpn\nautoload -Uz bashcompinit\nbashcompinit\n\n" + bash_script


def legacy_dispatch(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    mapping = {
        "user-add": ["user", "add"],
        "user-del": ["user", "del"],
        "user-list": ["user", "list"],
        "user-config": ["user", "config"],
        "user-info": ["user", "info"],
        "user-export": ["user", "export"],
        "status-summary": ["status", "--legacy-summary"],
        "sub-info": ["sub", "--legacy-summary"],
    }
    if argv[0] in mapping:
        return [*mapping[argv[0]], *argv[1:]]
    return argv


def panel_view() -> None:
    print_sub_summary()
    print()
    print_status_summary()


def interactive_panel() -> None:
    while True:
        os.system("clear")
        panel_view()
        print()
        print(paint("Panel", "bold", "cyan"))
        print("1) user list")
        print("2) user add")
        print("3) user del")
        print("4) user info")
        print("5) user config")
        print("6) logs")
        print("7) user usage")
        print("8) user quota")
        print("9) user suspend/resume")
        print("q) quit")
        choice = input("> ").strip().lower()
        if choice == "1":
            print()
            print_user_list()
            input("\nEnter to continue...")
        elif choice == "2":
            name = input("user name: ").strip()
            if name:
                info = user_add(name)
                print()
                print(f"created user: {info['name']}")
                print_user_info(name, show_qr=False)
                input("\nEnter to continue...")
        elif choice == "3":
            name = input("user name: ").strip()
            if name:
                user_del(name)
                print(f"deleted user: {name}")
                input("\nEnter to continue...")
        elif choice == "4":
            name = input("user name: ").strip()
            if name:
                print()
                print_user_info(name, show_qr=False)
                input("\nEnter to continue...")
        elif choice == "5":
            name = input("user name: ").strip()
            if name:
                print()
                print_user_config(name)
                input("\nEnter to continue...")
        elif choice == "6":
            print()
            for line in fetch_logs("xray.service"):
                print(line)
            input("\nEnter to continue...")
        elif choice == "7":
            name = input("user name (empty for all): ").strip()
            print()
            print_user_usage(name or None)
            input("\nEnter to continue...")
        elif choice == "8":
            name = input("user name: ").strip()
            quota_gb = input("quota in GB (empty to disable): ").strip()
            if name:
                quota_bytes = None if not quota_gb else int(float(quota_gb) * 1024 * 1024 * 1024)
                set_user_quota(name, quota_bytes)
                print_user_usage(name)
                input("\nEnter to continue...")
        elif choice == "9":
            name = input("user name: ").strip()
            action = input("action (suspend/resume): ").strip().lower()
            if name and action in {"suspend", "resume"}:
                set_user_suspension(name, action == "suspend", reason="manual")
                print_user_usage(name)
                input("\nEnter to continue...")
        elif choice in {"q", "quit", "exit"}:
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vpn")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install")
    sub.add_parser("panel")
    sub.add_parser("update")
    sub.add_parser("render-services")

    p_completion = sub.add_parser("completion")
    p_completion.add_argument("shell", nargs="?", choices=("bash", "zsh"))

    p_sub = sub.add_parser("sub")
    p_sub.add_argument("--json", action="store_true", dest="as_json")
    p_sub.add_argument("--legacy-summary", action="store_true", help=argparse.SUPPRESS)

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true", dest="as_json")
    p_status.add_argument("--legacy-summary", action="store_true", help=argparse.SUPPRESS)

    p_logs = sub.add_parser("logs")
    p_logs.add_argument("service", nargs="?", default="xray.service")
    p_logs.add_argument("--json", action="store_true", dest="as_json")

    p_uninstall = sub.add_parser("uninstall")
    p_uninstall.add_argument("--yes", action="store_true")

    p_user = sub.add_parser("user")
    user_sub = p_user.add_subparsers(dest="user_command", required=True)

    p_add = user_sub.add_parser("add")
    p_add.add_argument("name")
    p_add.add_argument("--json", action="store_true", dest="as_json")
    p_add.add_argument("--no-qr", action="store_true")

    p_del = user_sub.add_parser("del")
    p_del.add_argument("name")
    p_del.add_argument("--json", action="store_true", dest="as_json")

    p_list = user_sub.add_parser("list")
    p_list.add_argument("--json", action="store_true", dest="as_json")

    p_config = user_sub.add_parser("config")
    p_config.add_argument("name")
    p_config.add_argument("--json", action="store_true", dest="as_json")

    p_info = user_sub.add_parser("info")
    p_info.add_argument("name")
    p_info.add_argument("--json", action="store_true", dest="as_json")
    p_info.add_argument("--no-qr", action="store_true")

    p_export = user_sub.add_parser("export")
    p_export.add_argument("name")
    p_export.add_argument("--zip", action="store_true")
    p_export.add_argument("--json", action="store_true", dest="as_json")

    p_usage = user_sub.add_parser("usage")
    p_usage.add_argument("name", nargs="?")
    p_usage.add_argument("--json", action="store_true", dest="as_json")

    p_limit = user_sub.add_parser("limit")
    p_limit.add_argument("name")
    p_limit.add_argument("--quota-gb", type=float)
    p_limit.add_argument("--quota-bytes", type=int)
    p_limit.add_argument("--disable", action="store_true")
    p_limit.add_argument("--json", action="store_true", dest="as_json")

    p_suspend = user_sub.add_parser("suspend")
    p_suspend.add_argument("name")
    p_suspend.add_argument("--json", action="store_true", dest="as_json")

    p_resume = user_sub.add_parser("resume")
    p_resume.add_argument("name")
    p_resume.add_argument("--json", action="store_true", dest="as_json")

    p_reset_usage = user_sub.add_parser("reset-usage")
    p_reset_usage.add_argument("name")
    p_reset_usage.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main() -> None:
    argv = legacy_dispatch(sys.argv[1:])
    parser = build_parser()

    if not argv:
        if sys.stdin.isatty() and sys.stdout.isatty():
            interactive_panel()
            return
        parser.print_help()
        return

    args = parser.parse_args(argv)

    if args.command == "install":
        install_stack()
        return
    if args.command == "update":
        update_stack()
        return
    if args.command == "render-services":
        render_services()
        return
    if args.command == "completion":
        print(completion_script(detect_completion_shell(args.shell)))
        return
    if args.command == "panel":
        if sys.stdin.isatty() and sys.stdout.isatty():
            interactive_panel()
        else:
            panel_view()
        return
    if args.command == "sub":
        data = sub_payload()
        if args.as_json:
            print_json("sub", data)
        else:
            print_sub_summary(legacy=args.legacy_summary)
        return
    if args.command == "status":
        data = status_payload()
        if args.as_json:
            print_json("status", data)
        else:
            print_status_summary(legacy=args.legacy_summary)
        return
    if args.command == "logs":
        data = {"service": args.service, "lines": fetch_logs(args.service)}
        if args.as_json:
            print_json("logs", data)
        else:
            print("\n".join(data["lines"]))
        return
    if args.command == "uninstall":
        uninstall_stack(yes=args.yes)
        return

    if args.command != "user":
        raise SystemExit(f"unknown command: {args.command}")

    if args.user_command == "add":
        info = user_add(args.name)
        if args.as_json:
            print_json("user", info, message=f"created user: {args.name}")
        else:
            print(paint(f"created user: {args.name}", "green", "bold"))
            print()
            print_user_info(args.name, show_qr=not args.no_qr)
        return
    if args.user_command == "del":
        user_del(args.name)
        data = {"name": sanitize_name(args.name)}
        if args.as_json:
            print_json("user", data, message=f"deleted user: {args.name}")
        else:
            print(f"deleted user: {args.name}")
        return
    if args.user_command == "list":
        env = load_env()
        usage = user_usage_payload(refresh=True)
        data = [user_summary(user, env, usage.get(_name)) for _name, user in sorted(load_db()["users"].items())]
        if args.as_json:
            print_json("users", data)
        else:
            print_user_list()
        return
    if args.user_command == "config":
        data = user_file_payload(args.name)
        if args.as_json:
            print_json("user_config", data)
        else:
            print_user_config(args.name)
        return
    if args.user_command == "info":
        data = user_info_payload(args.name)
        if args.as_json:
            print_json("user_info", data)
        else:
            print_user_info(args.name, show_qr=not args.no_qr)
        return
    if args.user_command == "export":
        data = user_export_payload(args.name, args.zip)
        if args.as_json:
            print_json("user_export", data)
        else:
            print(data["archive_path"] or data["user_dir"])
        return
    if args.user_command == "usage":
        data = user_usage_payload(args.name, refresh=True)
        if args.as_json:
            print_json("user_usage", data)
        else:
            print_user_usage(args.name)
        return
    if args.user_command == "limit":
        chosen = [args.quota_gb is not None, args.quota_bytes is not None, args.disable]
        if sum(chosen) != 1:
            raise SystemExit("choose exactly one of --quota-gb, --quota-bytes or --disable")
        quota_bytes = None
        if args.quota_gb is not None:
            quota_bytes = max(int(args.quota_gb * 1024 * 1024 * 1024), 0)
        elif args.quota_bytes is not None:
            quota_bytes = max(int(args.quota_bytes), 0)
        data = set_user_quota(args.name, quota_bytes)
        if args.as_json:
            print_json("user_limit", data)
        else:
            print_user_usage(args.name)
        return
    if args.user_command == "suspend":
        data = set_user_suspension(args.name, True, reason="manual")
        if args.as_json:
            print_json("user_state", data, message=f"suspended user: {args.name}")
        else:
            print_user_usage(args.name)
        return
    if args.user_command == "resume":
        data = set_user_suspension(args.name, False, reason="manual")
        if args.as_json:
            print_json("user_state", data, message=f"resumed user: {args.name}")
        else:
            print_user_usage(args.name)
        return
    if args.user_command == "reset-usage":
        data = reset_user_usage(args.name)
        if args.as_json:
            print_json("user_usage", data, message=f"reset usage: {args.name}")
        else:
            print_user_usage(args.name)
        return

    raise SystemExit(f"unknown user command: {args.user_command}")


if __name__ == "__main__":
    main()
