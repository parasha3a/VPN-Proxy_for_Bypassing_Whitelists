from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "vpn_manager.py"
SPEC = importlib.util.spec_from_file_location("vpn_manager", MODULE_PATH)
vpn_manager = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(vpn_manager)


def sample_env() -> dict[str, str]:
    return {
        "SERVER_NAME": "MyVPN",
        "SERVER_IP": "203.0.113.10",
        "SERVER_HOST": "vpn.example.com",
        "SUB_PORT": "8000",
        "XRAY_PORT_REALITY": "443",
        "XRAY_PORT_XHTTP": "8443",
        "XRAY_PORT_WS": "8444",
        "XRAY_PORT_GRPC": "8445",
        "XRAY_PORT_VMESS": "8446",
        "XRAY_REALITY_SNI": "www.microsoft.com",
        "XRAY_REALITY_FINGERPRINT": "chrome",
        "XRAY_REALITY_PUBLIC_KEY": "PUBLICKEY",
        "XRAY_REALITY_SHORT_ID": "0123456789abcdef",
        "XRAY_XHTTP_PATH": "/vless-xhttp",
        "XRAY_WS_PATH": "/vless-ws",
        "XRAY_GRPC_SERVICE": "vless-grpc",
        "XRAY_VMESS_WS_PATH": "/vmess-ws",
        "HY2_PORT": "443",
        "HY2_UP_MBPS": "100",
        "HY2_DOWN_MBPS": "100",
        "HY2_OBFS_PASSWORD": "obfs-secret",
        "HY2_TLS_SNI": "vpn.example.com",
        "HY2_PIN_SHA256": "PIN",
        "HTTP_PROXY_PORT": "8080",
        "SOCKS5_PROXY_PORT": "1080",
        "MTPROTO_PORT": "8447",
        "MTPROTO_SECRET": "SECRET",
        "WG_SERVER_PORT": "51820",
        "WG_DNS": "1.1.1.1,8.8.8.8",
        "WG_SERVER_PUBLIC_KEY": "WG_PUBLIC",
    }


def sample_user() -> dict[str, str]:
    return {
        "name": "alice",
        "created": "2026-03-31T10:00:00+00:00",
        "uuid": "11111111-1111-1111-1111-111111111111",
        "email": "alice@vpn.local",
        "proxy_username": "alice",
        "proxy_password": "proxy-pass",
        "hy2_username": "alice",
        "hy2_password": "hy2-pass",
        "wg_private_key": "WG_PRIVATE",
        "wg_public_key": "WG_PUB",
        "wg_preshared_key": "WG_PSK",
        "wg_ipv4": "10.66.0.2/24",
        "wg_ipv6": "fd10:66::2/64",
    }


class VpnManagerTests(unittest.TestCase):
    def test_user_usage_payload_returns_mapping_when_name_omitted(self) -> None:
        original_usage_snapshot = vpn_manager.usage_snapshot
        vpn_manager.usage_snapshot = lambda refresh=True: {
            "bob": {"name": "bob", "total_bytes": 40},
            "alice": {"name": "alice", "total_bytes": 120},
        }
        try:
            usage = vpn_manager.user_usage_payload(refresh=True)
        finally:
            vpn_manager.usage_snapshot = original_usage_snapshot

        self.assertEqual(list(usage.keys()), ["alice", "bob"])
        self.assertEqual(usage["alice"]["total_bytes"], 120)

    def test_status_payload_uses_usage_mapping_for_top_usage(self) -> None:
        original_load_db = vpn_manager.load_db
        original_load_env = vpn_manager.load_env
        original_user_usage_payload = vpn_manager.user_usage_payload
        original_service_state = vpn_manager.service_state
        original_server_load_payload = vpn_manager.server_load_payload
        vpn_manager.load_db = lambda: {"users": {"alice": sample_user(), "bob": sample_user() | {"name": "bob"}}}
        vpn_manager.load_env = sample_env
        vpn_manager.user_usage_payload = lambda refresh=True: {
            "alice": {"name": "alice", "total_bytes": 120, "state": "active", "quota_bytes": None},
            "bob": {"name": "bob", "total_bytes": 240, "state": "active", "quota_bytes": None},
        }
        vpn_manager.service_state = lambda _service: "active"
        vpn_manager.server_load_payload = lambda: {
            "cpu": {"load1": 0.1, "load5": 0.2, "load15": 0.3},
            "memory": {"used_bytes": 1, "total_bytes": 2, "used_percent": 50},
            "disk": {"used_bytes": 3, "total_bytes": 4, "used_percent": 75},
            "network": {"rx_bytes": 5, "tx_bytes": 6},
        }
        try:
            payload = vpn_manager.status_payload()
        finally:
            vpn_manager.load_db = original_load_db
            vpn_manager.load_env = original_load_env
            vpn_manager.user_usage_payload = original_user_usage_payload
            vpn_manager.service_state = original_service_state
            vpn_manager.server_load_payload = original_server_load_payload

        self.assertEqual(payload["top_usage"][0]["name"], "bob")
        self.assertEqual(payload["users"], 2)

    def test_user_info_payload_reads_usage_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            users_dir = Path(tmp)
            user_dir = users_dir / "alice"
            user_dir.mkdir()
            for path in vpn_manager.bundle_file_index(user_dir).values():
                path.write_text("sample\n", encoding="utf-8")
            (user_dir / "uris.txt").write_text("vless://one\nvless://two\n", encoding="utf-8")
            (user_dir / "README.txt").write_text("bundle readme\n", encoding="utf-8")

            original_users_dir = vpn_manager.USERS_DIR
            original_load_db = vpn_manager.load_db
            original_load_env = vpn_manager.load_env
            original_user_usage_payload = vpn_manager.user_usage_payload
            vpn_manager.USERS_DIR = users_dir
            vpn_manager.load_db = lambda: {"users": {"alice": sample_user()}}
            vpn_manager.load_env = sample_env
            vpn_manager.user_usage_payload = lambda refresh=True: {
                "alice": {"name": "alice", "total_bytes": 512, "state": "active", "updated_at": "2026-04-01 12:00:00"},
            }
            try:
                payload = vpn_manager.user_info_payload("alice")
            finally:
                vpn_manager.USERS_DIR = original_users_dir
                vpn_manager.load_db = original_load_db
                vpn_manager.load_env = original_load_env
                vpn_manager.user_usage_payload = original_user_usage_payload

        self.assertEqual(payload["usage"]["total_bytes"], 512)
        self.assertEqual(payload["shareable_uris"], ["vless://one", "vless://two"])

    def test_build_singbox_client_has_dns_and_direct_rules(self) -> None:
        config = vpn_manager.build_singbox_client(sample_user(), sample_env())

        self.assertEqual(config["dns"]["strategy"], "prefer_ipv4")
        server_tags = {item["tag"] for item in config["dns"]["servers"]}
        self.assertIn("local-dns", server_tags)
        self.assertIn("remote-dns", server_tags)
        self.assertTrue(any(rule.get("ip_is_private") for rule in config["route"]["rules"]))
        self.assertTrue(any("local" in rule.get("domain_suffix", []) for rule in config["route"]["rules"]))

    def test_bundle_index_contains_named_files(self) -> None:
        index = vpn_manager.bundle_file_index(Path("/tmp/example-user"))

        self.assertEqual(index["xray"].name, "xray_client.json")
        self.assertEqual(index["singbox"].name, "singbox_client.json")
        self.assertEqual(index["hy2"].name, "hy2_client.yaml")
        self.assertEqual(index["wg"].name, "wg.conf")
        self.assertEqual(index["awg"].name, "awg.conf")
        self.assertEqual(index["proxy"].name, "proxy.txt")
        self.assertEqual(index["mtproto"].name, "mtproto.txt")

    def test_build_readme_mentions_client_mapping(self) -> None:
        readme = vpn_manager.build_readme(sample_user(), sample_env(), vpn_manager.build_uris(sample_user(), sample_env()))

        self.assertIn("xray_client.json -> AmneziaVPN", readme)
        self.assertIn("singbox_client.json -> Streisand", readme)
        self.assertIn("proxy.txt -> HTTP/SOCKS5 apps", readme)
        self.assertIn("mtproto.txt -> Telegram", readme)

    def test_legacy_dispatch_maps_old_commands(self) -> None:
        self.assertEqual(vpn_manager.legacy_dispatch(["user-add", "alice"]), ["user", "add", "alice"])
        self.assertEqual(vpn_manager.legacy_dispatch(["user-del", "alice"]), ["user", "del", "alice"])
        self.assertEqual(vpn_manager.legacy_dispatch(["status-summary"]), ["status", "--legacy-summary"])
        self.assertEqual(vpn_manager.legacy_dispatch(["sub-info"]), ["sub", "--legacy-summary"])

    def test_completion_script_supports_bash_and_zsh(self) -> None:
        bash_script = vpn_manager.completion_script("bash")
        zsh_script = vpn_manager.completion_script("zsh")

        self.assertIn("complete -F _vpn_complete vpn", bash_script)
        self.assertIn("#compdef vpn", zsh_script)
        self.assertIn("user config", bash_script)

    def test_build_xray_server_adds_warp_outbound_and_route_when_enabled(self) -> None:
        env = sample_env() | {
            "XRAY_API_LISTEN": "127.0.0.1:10085",
            "XRAY_REALITY_TARGET": "www.microsoft.com:443",
            "XRAY_REALITY_PRIVATE_KEY": "PRIVATEKEY",
            "XRAY_WARP_ENABLE": "1",
            "XRAY_WARP_PORT": "40000",
            "XRAY_WARP_DOMAINS": "gemini.google.com,aistudio.google.com",
        }
        server = vpn_manager.build_xray_server({"alice": sample_user()}, env)

        warp_outbound = next(item for item in server["outbounds"] if item.get("tag") == "warp")
        self.assertEqual(warp_outbound["protocol"], "socks")
        self.assertEqual(warp_outbound["settings"]["servers"][0]["port"], 40000)
        self.assertTrue(any(rule.get("outboundTag") == "warp" for rule in server["routing"]["rules"]))

    def test_parse_xray_stats_output_groups_bytes_by_user(self) -> None:
        raw = """
        {
          "stat": [
            {"name": "user>>>alice@vpn.local>>>traffic>>>uplink", "value": "100"},
            {"name": "user>>>alice@vpn.local>>>traffic>>>downlink", "value": "250"},
            {"name": "user>>>bob@vpn.local>>>traffic>>>uplink", "value": "40"}
          ]
        }
        """
        parsed = vpn_manager.parse_xray_stats_output(raw)

        self.assertEqual(parsed["alice@vpn.local"]["uplink"], 100)
        self.assertEqual(parsed["alice@vpn.local"]["downlink"], 250)
        self.assertEqual(parsed["bob@vpn.local"]["uplink"], 40)

    def test_apply_quota_enforcement_suspends_over_limit_users(self) -> None:
        data = {
            "users": {
                "alice": {"name": "alice", "email": "alice@vpn.local", "quota_bytes": 1000},
                "bob": {"name": "bob", "email": "bob@vpn.local", "quota_bytes": 5000},
            }
        }
        usage = {
            "alice": {"total_bytes": 1200},
            "bob": {"total_bytes": 4000},
        }

        changed = vpn_manager.apply_quota_enforcement(data, usage)

        self.assertTrue(changed)
        self.assertTrue(data["users"]["alice"]["suspended"])
        self.assertFalse(data["users"]["bob"].get("suspended", False))

    def test_server_load_payload_has_cpu_memory_disk_and_network(self) -> None:
        payload = vpn_manager.server_load_payload()

        self.assertIn("cpu", payload)
        self.assertIn("memory", payload)
        self.assertIn("disk", payload)
        self.assertIn("network", payload)


if __name__ == "__main__":
    unittest.main()
