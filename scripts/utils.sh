#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "error: $*" >&2
  exit 1
}

require_root() {
  [[ ${EUID:-$(id -u)} -eq 0 ]] || die "root privileges are required"
}

ensure_project_layout() {
  local root="$1"
  mkdir -p \
    "$root/scripts" \
    "$root/templates" \
    "$root/users" \
    "$root/data/generated"
  [[ -f "$root/data/users.json" ]] || printf '{\n  "users": {}\n}\n' >"$root/data/users.json"
  [[ -f "$root/data/server.env" ]] || cat >"$root/data/server.env" <<'EOF'
SERVER_NAME=MyVPN
SERVER_IP=127.0.0.1
SERVER_HOST=127.0.0.1
SERVER_NIC=eth0
SUB_PORT=8000
XRAY_PORT_REALITY=443
XRAY_PORT_XHTTP=8443
XRAY_PORT_WS=8444
XRAY_PORT_GRPC=8445
XRAY_PORT_VMESS=8446
XRAY_API_LISTEN=127.0.0.1:10085
XRAY_REALITY_SNI=www.microsoft.com
XRAY_REALITY_FINGERPRINT=chrome
XRAY_REALITY_TARGET=www.microsoft.com:443
XRAY_REALITY_PUBLIC_KEY=CHANGE_ME
XRAY_REALITY_PRIVATE_KEY=CHANGE_ME
XRAY_REALITY_SHORT_ID=0123456789abcdef
XRAY_XHTTP_PATH=/vless-xhttp
XRAY_WS_PATH=/vless-ws
XRAY_GRPC_SERVICE=vless-grpc
XRAY_VMESS_WS_PATH=/vmess-ws
HY2_PORT=443
HY2_TLS_SNI=127.0.0.1
HY2_OBFS_PASSWORD=CHANGE_ME
HY2_UP_MBPS=100
HY2_DOWN_MBPS=100
HY2_MASQUERADE_URL=https://www.microsoft.com/
HY2_PIN_SHA256=CHANGE_ME
HY2_CERT_PATH=/etc/hysteria/server.crt
HY2_KEY_PATH=/etc/hysteria/server.key
HY2_CONFIG_PATH=/etc/hysteria/config.yaml
HTTP_PROXY_PORT=8080
SOCKS5_PROXY_PORT=1080
MTPROTO_PORT=8447
MTPROTO_SECRET=CHANGE_ME
MTPROTO_DOMAIN=www.cloudflare.com
WG_SERVER_PORT=51820
WG_SERVER_PRIVATE_KEY=CHANGE_ME
WG_SERVER_PUBLIC_KEY=CHANGE_ME
WG_SERVER_ADDRESS=10.66.0.1/24
WG_SERVER_ADDRESS6=fd10:66::1/64
WG_CLIENT_NET=10.66.0.0/24
WG_CLIENT_NET6=fd10:66::/64
WG_DNS=1.1.1.1,8.8.8.8
AWG_JC=5
AWG_JMIN=32
AWG_JMAX=128
AWG_S1=64
AWG_S2=96
AWG_H1=1234567891
AWG_H2=1234567892
AWG_H3=1234567893
AWG_H4=1234567894
XRAY_CONFIG_PATH=/usr/local/etc/xray/config.json
THREEPROXY_CONFIG_PATH=/etc/3proxy/3proxy.cfg
WG_SERVER_CONFIG_PATH=/etc/wireguard/wg0.conf
AWG_SERVER_CONFIG_PATH=/etc/amnezia/awg0.conf
BOT_TOKEN=
ADMIN_CHAT_ID=
EOF
}

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  set -a
  # shellcheck source=/dev/null
  source "$file"
  set +a
}

service_state() {
  local service="$1"
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl-unavailable"
    return 0
  fi
  systemctl is-active "$service" 2>/dev/null || true
}

print_single_service() {
  local service="$1"
  printf '  %-20s %s\n' "$service" "$(service_state "$service")"
}

print_status() {
  local root="$1"
  local py="python3"
  [[ -x "$(command -v python3 || true)" ]] || py="python"

  "$py" "$root/scripts/vpn_manager.py" status-summary
  echo
  echo "Services:"
  print_single_service xray.service
  print_single_service hysteria.service
  print_single_service vpn-sub.service
  print_single_service 3proxy.service
  print_single_service mtg.service
  print_single_service wg-quick@wg0.service
  print_single_service awg-quick@awg0.service
  print_single_service vpn-bot.service
}

print_logs() {
  local service="${1:-xray.service}"
  if ! command -v journalctl >/dev/null 2>&1; then
    die "journalctl is not available on this system"
  fi
  journalctl -u "$service" -n 50 --no-pager
}

render_service_configs() {
  local root="$1"
  python3 "$root/scripts/vpn_manager.py" render-services
}

copy_if_possible() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" ]] || return 0
  local dst_dir
  dst_dir="$(dirname -- "$dst")"
  mkdir -p "$dst_dir"
  cp "$src" "$dst"
}

sync_xray_service() {
  local root="$1"
  load_env_file "$root/data/server.env"
  local rendered="$root/data/generated/xray_server.json"
  [[ -f "$rendered" ]] || return 0

  if [[ -n "${XRAY_CONFIG_PATH:-}" && -w "$(dirname -- "$XRAY_CONFIG_PATH")" ]]; then
    copy_if_possible "$rendered" "$XRAY_CONFIG_PATH"
  fi

  if command -v xray >/dev/null 2>&1 && [[ -n "${XRAY_CONFIG_PATH:-}" && -f "${XRAY_CONFIG_PATH}" ]]; then
    xray run -test -config "$XRAY_CONFIG_PATH" >/dev/null 2>&1 || die "xray config validation failed"
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files xray.service >/dev/null 2>&1; then
    systemctl restart xray.service || true
  fi
}

sync_3proxy_service() {
  local root="$1"
  load_env_file "$root/data/server.env"
  local rendered="$root/data/generated/3proxy.cfg"
  [[ -f "$rendered" ]] || return 0

  if [[ -n "${THREEPROXY_CONFIG_PATH:-}" && -w "$(dirname -- "$THREEPROXY_CONFIG_PATH")" ]]; then
    copy_if_possible "$rendered" "$THREEPROXY_CONFIG_PATH"
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 3proxy.service >/dev/null 2>&1; then
    systemctl restart 3proxy.service || true
  fi
}

sync_hysteria_service() {
  local root="$1"
  load_env_file "$root/data/server.env"
  local rendered="$root/data/generated/hysteria_server.yaml"
  [[ -f "$rendered" ]] || return 0

  if [[ -n "${HY2_CONFIG_PATH:-}" && -w "$(dirname -- "$HY2_CONFIG_PATH")" ]]; then
    copy_if_possible "$rendered" "$HY2_CONFIG_PATH"
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files hysteria.service >/dev/null 2>&1; then
    systemctl restart hysteria.service || true
  fi
}

sync_wireguard_service() {
  local root="$1"
  load_env_file "$root/data/server.env"
  local rendered="$root/data/generated/wg_server.conf"
  [[ -f "$rendered" ]] || return 0

  if [[ -n "${WG_SERVER_CONFIG_PATH:-}" && -w "$(dirname -- "$WG_SERVER_CONFIG_PATH")" ]]; then
    copy_if_possible "$rendered" "$WG_SERVER_CONFIG_PATH"
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files wg-quick@wg0.service >/dev/null 2>&1; then
    systemctl restart wg-quick@wg0.service || true
  fi
}

sync_amneziawg_service() {
  local root="$1"
  load_env_file "$root/data/server.env"
  local rendered="$root/data/generated/awg_server.conf"
  [[ -f "$rendered" ]] || return 0

  if [[ -n "${AWG_SERVER_CONFIG_PATH:-}" && -w "$(dirname -- "$AWG_SERVER_CONFIG_PATH")" ]]; then
    copy_if_possible "$rendered" "$AWG_SERVER_CONFIG_PATH"
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files awg-quick@awg0.service >/dev/null 2>&1; then
    systemctl restart awg-quick@awg0.service || true
  fi
}

render_terminal_qrs() {
  local root="$1"
  local name="$2"
  local user_dir="$root/users/$name"
  [[ -d "$user_dir" ]] || die "user '$name' not found"
  command -v qrencode >/dev/null 2>&1 || return 0

  echo
  echo "[QR] Subscription"
  qrencode -t ANSIUTF8 <"$user_dir/subscription_url.txt" || true
  echo
  echo "[QR] VLESS Reality"
  head -n 1 "$user_dir/uris.txt" | qrencode -t ANSIUTF8 || true
  echo
  echo "[QR] WireGuard"
  qrencode -t ANSIUTF8 <"$user_dir/wg.conf" || true
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo "64" ;;
    aarch64|arm64) echo "arm64-v8a" ;;
    armv7l) echo "arm32-v7a" ;;
    *) die "unsupported architecture: $(uname -m)" ;;
  esac
}

github_latest_asset() {
  local repo="$1"
  local pattern="$2"
  python3 - "$repo" "$pattern" <<'PY'
import json
import sys
from urllib.request import urlopen

repo, pattern = sys.argv[1], sys.argv[2]
url = f"https://api.github.com/repos/{repo}/releases/latest"
with urlopen(url) as resp:
    data = json.load(resp)
for asset in data.get("assets", []):
    name = asset.get("name", "")
    if pattern in name:
        print(asset["browser_download_url"])
        break
else:
    raise SystemExit(f"no asset found for pattern: {pattern}")
PY
}

download_file() {
  local url="$1"
  local dst="$2"
  curl -fsSL "$url" -o "$dst"
}

uninstall_stack() {
  local root="$1"
  read -r -p "Remove services and generated configs? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || exit 0

  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now vpn-bot.service vpn-sub.service mtg.service 3proxy.service xray.service hysteria.service wg-quick@wg0.service awg-quick@awg0.service 2>/dev/null || true
  fi

  rm -f /usr/local/bin/vpn
  rm -f /etc/systemd/system/vpn-sub.service
  rm -f /etc/systemd/system/vpn-bot.service
  rm -f /etc/systemd/system/hysteria.service
  systemctl daemon-reload 2>/dev/null || true

  echo "Stack services removed. Project files remain in: $root"
}
