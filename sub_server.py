#!/usr/bin/env python3
from __future__ import annotations

import base64
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
USERS_DIR = ROOT / "users"
HOST = os.getenv("VPN_SUB_HOST", "0.0.0.0")
PORT = int(os.getenv("VPN_SUB_PORT", "8000"))


def load_user_raw(name: str) -> bytes:
    path = USERS_DIR / name / "uris.txt"
    if not path.exists():
        raise FileNotFoundError(name)
    return path.read_bytes()


class Handler(BaseHTTPRequestHandler):
    server_version = "vpn-sub/0.1"

    def send_body(self, body: bytes, content_type: str = "text/plain; charset=utf-8", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_body(b"OK\n")
            return

        path = self.path.rstrip("/")
        if not path.startswith("/sub/"):
            self.send_body(b"not found\n", code=404)
            return

        raw_mode = path.endswith("/raw")
        name = unquote(path.split("/")[2])
        try:
            raw = load_user_raw(name)
        except FileNotFoundError:
            self.send_body(b"user not found\n", code=404)
            return

        if raw_mode:
            self.send_body(raw)
        else:
            payload = base64.b64encode(raw) + b"\n"
            self.send_body(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
