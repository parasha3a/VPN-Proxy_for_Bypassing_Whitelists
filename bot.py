#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / "data" / "server.env"
VPN = ROOT / "vpn.sh"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


ENV = load_env()
TOKEN = ENV.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = str(ENV.get("ADMIN_CHAT_ID", "")).strip()
API = f"https://api.telegram.org/bot{TOKEN}/"


def api_call(method: str, fields: dict[str, str] | None = None, files: dict[str, Path] | None = None) -> dict:
    fields = fields or {}
    files = files or {}
    if files:
        boundary = "----vpn-bot-boundary"
        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        for key, path in files.items():
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{key}"; filename="{path.name}"\r\n'.encode()
            )
            body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
            body.extend(path.read_bytes())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(
            API + method,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    else:
        payload = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(API + method, data=payload)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def send_text(chat_id: str, text: str) -> None:
    chunks = [text[i : i + 3500] for i in range(0, len(text), 3500)] or [""]
    for chunk in chunks:
        api_call("sendMessage", {"chat_id": chat_id, "text": chunk})


def send_photo(chat_id: str, path: Path, caption: str = "") -> None:
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    api_call("sendPhoto", fields, {"photo": path})


def send_document(chat_id: str, path: Path, caption: str = "") -> None:
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    api_call("sendDocument", fields, {"document": path})


def vpn_cmd(*args: str) -> str:
    proc = subprocess.run([str(VPN), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command failed")
    return proc.stdout.strip()


def user_dir(name: str) -> Path:
    return ROOT / "users" / name


def send_bundle(chat_id: str, name: str) -> None:
    base = user_dir(name)
    readme = (base / "README.txt").read_text()
    uris = (base / "uris.txt").read_text()
    send_text(chat_id, f"{(base / 'subscription_url.txt').read_text().strip()}\n\n{uris}".strip())
    if (base / "qr_sub.png").exists():
        send_photo(chat_id, base / "qr_sub.png", "Subscription QR")
    if (base / "qr_vless.png").exists():
        send_photo(chat_id, base / "qr_vless.png", "VLESS Reality QR")
    send_document(chat_id, base / "xray_client.json")
    send_document(chat_id, base / "singbox_client.json")
    send_document(chat_id, base / "hy2_client.yaml")
    send_document(chat_id, base / "awg.conf")
    send_document(chat_id, base / "wg.conf")
    send_text(chat_id, (base / "mtproto.txt").read_text().strip())
    send_text(chat_id, (base / "proxy.txt").read_text().strip())
    send_document(chat_id, base / "README.txt", readme[:512])


def handle_message(chat_id: str, text: str) -> None:
    parts = text.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        send_text(
            chat_id,
            "/add <name>\n/del <name>\n/list\n/info <name>\n/status\n/logs",
        )
    elif cmd == "/list":
        send_text(chat_id, vpn_cmd("user", "list"))
    elif cmd == "/status":
        send_text(chat_id, vpn_cmd("status"))
    elif cmd == "/logs":
        send_text(chat_id, vpn_cmd("logs"))
    elif cmd == "/add":
        if not arg:
            send_text(chat_id, "usage: /add <name>")
            return
        send_text(chat_id, vpn_cmd("user", "add", arg))
        send_bundle(chat_id, arg)
    elif cmd == "/del":
        if not arg:
            send_text(chat_id, "usage: /del <name>")
            return
        send_text(chat_id, vpn_cmd("user", "del", arg))
    elif cmd == "/info":
        if not arg:
            send_text(chat_id, "usage: /info <name>")
            return
        send_text(chat_id, vpn_cmd("user", "info", arg))
        send_bundle(chat_id, arg)
    else:
        send_text(chat_id, "unknown command")


def main() -> None:
    if not TOKEN or not ADMIN_CHAT_ID:
        raise SystemExit("BOT_TOKEN and ADMIN_CHAT_ID must be set in data/server.env")

    offset = 0
    while True:
        try:
            data = api_call("getUpdates", {"timeout": "30", "offset": str(offset)})
            for item in data.get("result", []):
                offset = item["update_id"] + 1
                message = item.get("message") or {}
                chat = str(message.get("chat", {}).get("id", ""))
                if chat != ADMIN_CHAT_ID:
                    continue
                text = message.get("text", "")
                if text:
                    try:
                        handle_message(chat, text)
                    except Exception as exc:  # pragma: no cover
                        send_text(chat, f"error: {exc}")
        except Exception:
            time.sleep(3)


if __name__ == "__main__":
    main()
