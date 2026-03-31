from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "sub_server.py"
SPEC = importlib.util.spec_from_file_location("sub_server", MODULE_PATH)
sub_server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(sub_server)


class SubServerTests(unittest.TestCase):
    def test_build_admin_html_contains_workspace_sections(self) -> None:
        html = sub_server.build_admin_html()

        self.assertIn("VPN Control Center", html)
        self.assertIn("Create user", html)
        self.assertIn("Config viewer", html)
        self.assertIn("Proxy surfaces", html)

    def test_resolve_bundle_path_supports_named_kinds_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            users_dir = Path(tmp)
            user_dir = users_dir / "alice"
            user_dir.mkdir()
            (user_dir / "xray_client.json").write_text("{}")

            original = sub_server.USERS_DIR
            sub_server.USERS_DIR = users_dir
            try:
                resolved = sub_server.resolve_bundle_path("alice", "xray")
                self.assertEqual(resolved.name, "xray_client.json")
                with self.assertRaises(FileNotFoundError):
                    sub_server.resolve_bundle_path("alice", "../secret")
            finally:
                sub_server.USERS_DIR = original

    def test_load_runtime_settings_reads_server_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "server.env"
            env_path.write_text(
                "SUB_PORT=9000\n"
                "VPN_PANEL_TOKEN=token123\n"
                "SERVER_HOST=vpn.example.com\n"
                "VPN_ADMIN_PORT=9443\n"
            )

            original = sub_server.SERVER_ENV_PATH
            sub_server.SERVER_ENV_PATH = env_path
            try:
                settings = sub_server.load_runtime_settings()
            finally:
                sub_server.SERVER_ENV_PATH = original

            self.assertEqual(settings["SUB_PORT"], "9000")
            self.assertEqual(settings["VPN_PANEL_TOKEN"], "token123")
            self.assertEqual(settings["SERVER_HOST"], "vpn.example.com")
            self.assertEqual(settings["VPN_ADMIN_PORT"], "9443")

    def test_rescue_feeds_have_mobile_and_mirror_links(self) -> None:
        feeds = sub_server.rescue_feeds()

        self.assertTrue(any(item["slug"] == "black-vless-mobile" for item in feeds))
        self.assertTrue(any(item["kind"] == "tor-bridges" for item in feeds))
        self.assertTrue(any("cdn.jsdelivr.net" in mirror for item in feeds for mirror in item["mirrors"]))

    def test_runtime_admin_defaults_to_localhost(self) -> None:
        self.assertEqual(sub_server.runtime_admin_host(), "127.0.0.1")
        self.assertEqual(sub_server.runtime_admin_port(), 8081)

    def test_security_headers_include_csp_and_frame_deny(self) -> None:
        headers = sub_server.security_headers(content_type="html")

        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_load_user_raw_denies_suspended_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            users_dir = Path(tmp)
            user_dir = users_dir / "alice"
            user_dir.mkdir()
            (user_dir / "uris.txt").write_text("vless://example")

            original_users_dir = sub_server.USERS_DIR
            original_load_db = sub_server.vpn_manager.load_db
            sub_server.USERS_DIR = users_dir
            sub_server.vpn_manager.load_db = lambda: {"users": {"alice": {"name": "alice", "suspended": True}}}
            try:
                with self.assertRaises(PermissionError):
                    sub_server.load_user_raw("alice")
            finally:
                sub_server.USERS_DIR = original_users_dir
                sub_server.vpn_manager.load_db = original_load_db


if __name__ == "__main__":
    unittest.main()
