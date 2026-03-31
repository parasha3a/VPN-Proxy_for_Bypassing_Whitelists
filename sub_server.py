#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
USERS_DIR = ROOT / "users"
SERVER_ENV_PATH = ROOT / "data" / "server.env"
WEB_DIR = ROOT / "web"

sys.path.insert(0, str(ROOT / "scripts"))
import vpn_manager  # noqa: E402


def load_runtime_settings() -> dict[str, str]:
    settings: dict[str, str] = {}
    if SERVER_ENV_PATH.exists():
        for line in SERVER_ENV_PATH.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    return settings


def runtime_host() -> str:
    return os.getenv("VPN_SUB_HOST") or load_runtime_settings().get("VPN_SUB_HOST") or "0.0.0.0"


def runtime_port() -> int:
    return int(os.getenv("VPN_SUB_PORT") or load_runtime_settings().get("SUB_PORT", "8000"))


def runtime_admin_host() -> str:
    return os.getenv("VPN_ADMIN_HOST") or load_runtime_settings().get("VPN_ADMIN_HOST") or "127.0.0.1"


def runtime_admin_port() -> int:
    return int(os.getenv("VPN_ADMIN_PORT") or load_runtime_settings().get("VPN_ADMIN_PORT", "8081"))


def admin_token() -> str:
    token = os.getenv("VPN_PANEL_TOKEN") or load_runtime_settings().get("VPN_PANEL_TOKEN", "")
    return token.strip()


def load_user_raw(name: str) -> bytes:
    safe_name = vpn_manager.sanitize_name(name)
    user = vpn_manager.load_db()["users"].get(safe_name)
    if not user:
        raise FileNotFoundError(safe_name)
    if user.get("suspended"):
        raise PermissionError(safe_name)
    path = USERS_DIR / safe_name / "uris.txt"
    if not path.exists():
        raise FileNotFoundError(safe_name)
    return path.read_bytes()


def build_admin_html() -> str:
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


def rescue_feeds() -> list[dict[str, object]]:
    return [
        {
            "slug": "black-vless-mobile",
            "title": "Black VLESS Mobile Top 150",
            "kind": "blacklist",
            "source": "igareck/vpn-configs-for-russia",
            "description": "Compact mobile VLESS feed for blacklist scenarios.",
            "primary": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
            "mirrors": [
                "https://cdn.jsdelivr.net/gh/igareck/vpn-configs-for-russia@main/BLACK_VLESS_RUS_mobile.txt",
                "https://cdn.statically.io/gh/igareck/vpn-configs-for-russia@main/BLACK_VLESS_RUS_mobile.txt",
                "https://rawcdn.githack.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt",
            ],
        },
        {
            "slug": "white-cidr-mobile-1",
            "title": "White CIDR Mobile Top 150 #1",
            "kind": "whitelist",
            "source": "igareck/vpn-configs-for-russia",
            "description": "Top-150 CIDR bypass feed for whitelist-only networks.",
            "primary": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
            "mirrors": [
                "https://cdn.jsdelivr.net/gh/igareck/vpn-configs-for-russia@main/Vless-Reality-White-Lists-Rus-Mobile.txt",
                "https://cdn.statically.io/gh/igareck/vpn-configs-for-russia@main/Vless-Reality-White-Lists-Rus-Mobile.txt",
                "https://rawcdn.githack.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
            ],
        },
        {
            "slug": "tor-bridges-top100",
            "title": "Tor Bridges Top 100",
            "kind": "tor-bridges",
            "source": "igareck/vpn-configs-for-russia",
            "description": "Emergency Tor bridge list for Orbot, Tor Browser and Invizible Pro.",
            "primary": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/TOR-BRIDGES/TOR_BRIDGES_TOP100.txt",
            "mirrors": [
                "https://cdn.jsdelivr.net/gh/igareck/vpn-configs-for-russia@main/TOR-BRIDGES/TOR_BRIDGES_TOP100.txt",
                "https://cdn.statically.io/gh/igareck/vpn-configs-for-russia@main/TOR-BRIDGES/TOR_BRIDGES_TOP100.txt",
                "https://rawcdn.githack.com/igareck/vpn-configs-for-russia/main/TOR-BRIDGES/TOR_BRIDGES_TOP100.txt",
            ],
        },
    ]


def resolve_bundle_path(name: str, kind: str) -> Path:
    user_name = vpn_manager.sanitize_name(name)
    user_dir = USERS_DIR / user_name
    if not user_dir.is_dir():
        raise FileNotFoundError(user_name)
    if kind == "zip":
        data = vpn_manager.user_export_payload(user_name, True)
        archive_path = data.get("archive_path")
        if not archive_path:
            raise FileNotFoundError("archive")
        return Path(archive_path)
    files = vpn_manager.bundle_file_index(user_dir)
    if kind not in files:
        raise FileNotFoundError(kind)
    path = files[kind]
    if not path.exists():
        raise FileNotFoundError(kind)
    return path


def usage_monitor_loop(interval_seconds: int = 60) -> None:
    interval = max(interval_seconds, 15)
    while True:
        try:
            vpn_manager.usage_snapshot(refresh=True)
        except Exception:
            pass
        time.sleep(interval)


def guess_content_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def json_bytes(data: object) -> bytes:
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def security_headers(*, content_type: str = "plain") -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
    if content_type == "html":
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "form-action 'self'"
        )
    return headers


class Handler(BaseHTTPRequestHandler):
    server_version = "vpn-control/0.2"

    def send_body(
        self,
        body: bytes,
        *,
        content_type: str = "text/plain; charset=utf-8",
        code: int = 200,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        merged_headers = {
            **security_headers(content_type="html" if content_type.startswith("text/html") else "plain"),
            **(extra_headers or {}),
        }
        for key, value in merged_headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data: object, *, code: int = 200) -> None:
        self.send_body(json_bytes(data), content_type="application/json; charset=utf-8", code=code)

    def send_error_json(self, error: Exception) -> None:
        if isinstance(error, PermissionError):
            self.send_json({"ok": False, "error": "user is suspended"}, code=403)
            return
        if isinstance(error, FileNotFoundError):
            self.send_json({"ok": False, "error": "not found"}, code=404)
            return
        if isinstance(error, SystemExit):
            self.send_json({"ok": False, "error": str(error)}, code=400)
            return
        if isinstance(error, ValueError):
            self.send_json({"ok": False, "error": str(error)}, code=400)
            return
        self.send_json({"ok": False, "error": "internal server error"}, code=500)

    def read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def request_path(self) -> str:
        return self.path.split("?", 1)[0]

    def request_parts(self) -> list[str]:
        path = self.request_path().strip("/")
        if not path:
            return []
        return [unquote(part) for part in path.split("/")]

    def require_admin_auth(self) -> bool:
        token = admin_token()
        if not token or token == "CHANGE_ME":
            self.send_json(
                {
                    "ok": False,
                    "error": "admin panel token is not configured",
                    "hint": "set VPN_PANEL_TOKEN in data/server.env",
                },
                code=503,
            )
            return False

        header = self.headers.get("Authorization", "")
        supplied = ""
        if header.lower().startswith("bearer "):
            supplied = header.split(" ", 1)[1].strip()
        if not supplied:
            supplied = self.headers.get("X-Panel-Token", "").strip()
        if supplied != token:
            self.send_json({"ok": False, "error": "unauthorized"}, code=401)
            return False
        return True

    def serve_static(self, relative_path: str) -> None:
        path = WEB_DIR / relative_path
        if not path.exists() or not path.is_file():
            self.send_body(b"not found\n", code=404)
            return
        self.send_body(path.read_bytes(), content_type=f"{guess_content_type(path)}; charset=utf-8")

    def handle_public_subscription(self) -> bool:
        if self.request_path() == "/health":
            self.send_body(b"OK\n")
            return True

        path = self.request_path().rstrip("/")
        if not path.startswith("/sub/"):
            return False

        raw_mode = path.endswith("/raw")
        parts = path.split("/")
        if len(parts) < 3:
            self.send_body(b"not found\n", code=404)
            return True
        name = unquote(parts[2])
        try:
            raw = load_user_raw(name)
        except FileNotFoundError:
            self.send_body(b"user not found\n", code=404)
            return True
        except PermissionError:
            self.send_body(b"user suspended\n", code=403)
            return True

        if raw_mode:
            self.send_body(raw)
        else:
            self.send_body(base64.b64encode(raw) + b"\n")
        return True

    def do_GET(self) -> None:  # noqa: N802
        try:
            if self.handle_public_subscription():
                return
            path = self.request_path()
            parts = self.request_parts()

            if path == "/":
                self.send_body(build_admin_html().encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if path == "/assets/admin.css":
                self.serve_static("admin.css")
                return
            if path == "/assets/admin.js":
                self.serve_static("admin.js")
                return

            if path.startswith("/api/") or path.startswith("/download/"):
                if not self.require_admin_auth():
                    return

            if parts == ["api", "overview"]:
                self.send_json(
                    {
                        "status": vpn_manager.status_payload(),
                        "sub": vpn_manager.sub_payload(),
                        "rescue_feeds": rescue_feeds(),
                    }
                )
                return

            if parts == ["api", "users"]:
                env = vpn_manager.load_env()
                usage = {item["name"]: item for item in vpn_manager.user_usage_payload(refresh=True)}
                items = [
                    vpn_manager.user_summary(user, env, usage.get(_name))
                    for _name, user in sorted(vpn_manager.load_db()["users"].items())
                ]
                self.send_json({"items": items})
                return

            if len(parts) == 3 and parts[:2] == ["api", "users"]:
                name = parts[2]
                self.send_json(vpn_manager.user_info_payload(name))
                return

            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "usage":
                self.send_json(vpn_manager.user_usage_payload(parts[2], refresh=True))
                return

            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "config":
                name = parts[2]
                self.send_json(vpn_manager.user_file_payload(name))
                return

            if len(parts) == 5 and parts[:2] == ["api", "users"] and parts[3] == "file":
                name, kind = parts[2], parts[4]
                file_path = resolve_bundle_path(name, kind)
                if kind == "zip":
                    self.send_json({"name": kind, "filename": file_path.name, "download_only": True})
                    return
                self.send_json(
                    {
                        "name": kind,
                        "filename": file_path.name,
                        "content": file_path.read_text(encoding="utf-8", errors="replace"),
                    }
                )
                return

            if len(parts) == 4 and parts[:2] == ["download", "users"]:
                name, kind = parts[2], parts[3]
                file_path = resolve_bundle_path(name, kind)
                headers = {"Content-Disposition": f'attachment; filename="{file_path.name}"'}
                self.send_body(file_path.read_bytes(), content_type=guess_content_type(file_path), extra_headers=headers)
                return

            self.send_body(b"not found\n", code=404)
        except (Exception, SystemExit) as error:  # pragma: no cover - covered via handler methods
            self.send_error_json(error)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parts = self.request_parts()
            if parts == ["api", "users"]:
                if not self.require_admin_auth():
                    return
                payload = self.read_json_body()
                name = str(payload.get("name", "")).strip()
                self.send_json(vpn_manager.user_add(name), code=201)
                return

            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "quota":
                if not self.require_admin_auth():
                    return
                payload = self.read_json_body()
                if payload.get("disable"):
                    quota_bytes = None
                elif "quota_bytes" in payload:
                    quota_bytes = max(int(payload["quota_bytes"]), 0)
                elif "quota_gb" in payload:
                    quota_bytes = max(int(float(payload["quota_gb"]) * 1024 * 1024 * 1024), 0)
                else:
                    raise ValueError("quota_bytes, quota_gb or disable is required")
                self.send_json(vpn_manager.set_user_quota(parts[2], quota_bytes))
                return

            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "suspend":
                if not self.require_admin_auth():
                    return
                self.send_json(vpn_manager.set_user_suspension(parts[2], True, reason="manual"))
                return

            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "resume":
                if not self.require_admin_auth():
                    return
                self.send_json(vpn_manager.set_user_suspension(parts[2], False, reason="manual"))
                return

            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "reset-usage":
                if not self.require_admin_auth():
                    return
                self.send_json(vpn_manager.reset_user_usage(parts[2]))
                return

            self.send_body(b"not found\n", code=404)
        except (Exception, SystemExit) as error:  # pragma: no cover - covered via handler methods
            self.send_error_json(error)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            parts = self.request_parts()
            if len(parts) == 3 and parts[:2] == ["api", "users"]:
                if not self.require_admin_auth():
                    return
                name = parts[2]
                vpn_manager.user_del(name)
                self.send_json({"ok": True, "name": vpn_manager.sanitize_name(name)})
                return

            self.send_body(b"not found\n", code=404)
        except (Exception, SystemExit) as error:  # pragma: no cover - covered via handler methods
            self.send_error_json(error)

    def log_message(self, fmt: str, *args: object) -> None:
        return


class PublicOnlyHandler(Handler):
    def do_GET(self) -> None:  # noqa: N802
        if self.handle_public_subscription():
            return
        self.send_body(b"not found\n", code=404)

    def do_POST(self) -> None:  # noqa: N802
        self.send_body(b"not found\n", code=404)

    def do_DELETE(self) -> None:  # noqa: N802
        self.send_body(b"not found\n", code=404)


class VPNThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=usage_monitor_loop, kwargs={"interval_seconds": 60}, daemon=True).start()
    public_address = (runtime_host(), runtime_port())
    admin_address = (runtime_admin_host(), runtime_admin_port())

    if public_address == admin_address:
        VPNThreadingHTTPServer(public_address, Handler).serve_forever()
    else:
        public_server = VPNThreadingHTTPServer(public_address, PublicOnlyHandler)
        threading.Thread(target=public_server.serve_forever, daemon=True).start()
        VPNThreadingHTTPServer(admin_address, Handler).serve_forever()
