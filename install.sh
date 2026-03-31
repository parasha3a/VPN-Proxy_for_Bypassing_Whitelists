#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

banner() {
  cat <<'EOF'
 __     ___ ____  _   _   ____             _             
 \ \   / / |  _ \| \ | | |  _ \  ___ _ __ | | ___  _   _ 
  \ \ / /| | |_) |  \| | | | | |/ _ \ '_ \| |/ _ \| | | |
   \ V / | |  __/| |\  | | |_| |  __/ |_) | | (_) | |_| |
    \_/  |_|_|   |_| \_| |____/ \___| .__/|_|\___/ \__, |
                                    |_|            |___/ 
EOF
}

detect_public_ip() {
  curl -fsSL https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}'
}

detect_nic() {
  ip route show default 2>/dev/null | awk '/default/ {print $5; exit}' || echo "eth0"
}

prompt_default() {
  local label="$1"
  local current="$2"
  local value
  read -r -p "$label [$current]: " value
  printf '%s' "${value:-$current}"
}

yes_no() {
  local label="$1"
  local default="$2"
  local value prompt
  prompt="$label [$default]: "
  read -r -p "$prompt" value
  value="${value:-$default}"
  [[ "$value" =~ ^[Yy]$ ]]
}

write_env_value() {
  local key="$1"
  local value="$2"
  python3 - "$ROOT_DIR/data/server.env" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text().splitlines()
for idx, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[idx] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n")
PY
}

random_token() {
  python3 - <<'PY'
import secrets
print(secrets.token_hex(16))
PY
}

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"

  if [[ ! -f /etc/debian_version ]]; then
    die "supported OS: Ubuntu 22.04+ or Debian 12+"
  fi

  banner
  local public_ip server_nic
  public_ip="$(detect_public_ip)"
  server_nic="$(detect_nic)"
  echo "Detected public IP: $public_ip"
  echo "Detected NIC: $server_nic"

  local server_name server_host nic install_wg install_bot install_warp
  server_name="$(prompt_default "Server name" "MyVPN")"
  server_host="$(prompt_default "Share host/IP" "$public_ip")"
  nic="$(prompt_default "Network interface" "$server_nic")"
  install_wg="N"
  install_bot="N"
  install_warp="N"

  echo
  echo "Port customization (Enter to keep defaults):"
  local port_reality port_xhttp port_ws port_grpc port_vmess port_hy2 port_http port_socks5 port_sub port_mtproto port_wg
  port_reality="$(prompt_default "  VLESS Reality port" "443")"
  port_xhttp="$(prompt_default "  VLESS XHTTP port" "8443")"
  port_ws="$(prompt_default "  VLESS WS port" "8444")"
  port_grpc="$(prompt_default "  VLESS gRPC port" "8445")"
  port_vmess="$(prompt_default "  VMess WS port" "8446")"
  port_hy2="$(prompt_default "  Hysteria2 UDP port" "443")"
  port_http="$(prompt_default "  HTTP proxy port" "8080")"
  port_socks5="$(prompt_default "  SOCKS5 proxy port" "1080")"
  port_sub="$(prompt_default "  Subscription server port" "8000")"
  port_mtproto="$(prompt_default "  MTProto port" "8447")"
  port_wg="$(prompt_default "  WireGuard port" "51820")"
  echo

  yes_no "Install plain WireGuard too?" "n" && install_wg="Y"
  yes_no "Enable selective Cloudflare WARP egress for problematic domains?" "n" && install_warp="Y"
  yes_no "Install Telegram bot?" "n" && install_bot="Y"

  write_env_value SERVER_NAME "$server_name"
  write_env_value SERVER_IP "$public_ip"
  write_env_value SERVER_HOST "$server_host"
  write_env_value SERVER_NIC "$nic"
  write_env_value VPN_SUB_HOST "0.0.0.0"
  write_env_value VPN_ADMIN_HOST "127.0.0.1"
  write_env_value VPN_ADMIN_PORT "8081"
  write_env_value VPN_FIREWALL_ENABLE "1"
  write_env_value VPN_FAIL2BAN_ENABLE "1"
  write_env_value VPN_SSH_PORT "22"
  write_env_value VPN_SSH_ALLOW_USERS "root"
  write_env_value VPN_SSH_PASSWORD_ONLY "1"
  write_env_value XRAY_PORT_REALITY "$port_reality"
  write_env_value XRAY_PORT_XHTTP "$port_xhttp"
  write_env_value XRAY_PORT_WS "$port_ws"
  write_env_value XRAY_PORT_GRPC "$port_grpc"
  write_env_value XRAY_PORT_VMESS "$port_vmess"
  write_env_value HY2_PORT "$port_hy2"
  write_env_value HY2_TLS_SNI "$server_host"
  write_env_value HTTP_PROXY_PORT "$port_http"
  write_env_value SOCKS5_PROXY_PORT "$port_socks5"
  write_env_value SUB_PORT "$port_sub"
  write_env_value MTPROTO_PORT "$port_mtproto"
  write_env_value WG_SERVER_PORT "$port_wg"
  write_env_value XRAY_WARP_ENABLE "$([[ "$install_warp" == "Y" ]] && echo 1 || echo 0)"
  if ! grep -q '^VPN_PANEL_TOKEN=' "$ROOT_DIR/data/server.env" || grep -q '^VPN_PANEL_TOKEN=CHANGE_ME$' "$ROOT_DIR/data/server.env"; then
    write_env_value VPN_PANEL_TOKEN "$(random_token)"
  fi

  echo
  echo "[x] Xray-core (VLESS Reality + XHTTP + WS + gRPC + VMess)"
  echo "[x] Hysteria2"
  echo "[x] AmneziaWG"
  if [[ "$install_wg" == "Y" ]]; then echo "[x] WireGuard plain"; else echo "[ ] WireGuard plain"; fi
  if [[ "$install_warp" == "Y" ]]; then echo "[x] Cloudflare WARP egress"; else echo "[ ] Cloudflare WARP egress"; fi
  echo "[x] HTTP + SOCKS5 proxy (3proxy)"
  echo "[x] MTProto (mtg)"
  echo "[x] Subscription server"
  if [[ "$install_bot" == "Y" ]]; then echo "[x] Telegram bot"; else echo "[ ] Telegram bot"; fi
  echo

  apt-get update
  apt-get install -y curl wget unzip tar ca-certificates python3 python3-venv jq qrencode uuid-runtime iproute2 iptables openssl gnupg openssh-server ufw fail2ban

  "$ROOT_DIR/scripts/install_network_tuning.sh"
  "$ROOT_DIR/scripts/install_xray.sh"
  "$ROOT_DIR/scripts/install_hysteria.sh"
  if [[ "$install_warp" == "Y" ]]; then
    "$ROOT_DIR/scripts/install_warp.sh"
  fi
  "$ROOT_DIR/scripts/install_awg.sh"
  if [[ "$install_wg" == "Y" ]]; then
    "$ROOT_DIR/scripts/install_wg.sh"
  fi
  "$ROOT_DIR/scripts/install_proxy.sh"
  "$ROOT_DIR/scripts/install_mtproto.sh"
  "$ROOT_DIR/scripts/install_sub.sh"

  if [[ "$install_bot" == "Y" ]]; then
    local bot_token admin_chat
    bot_token="$(prompt_default "Telegram bot token" "")"
    admin_chat="$(prompt_default "Telegram ADMIN_CHAT_ID" "")"
    write_env_value BOT_TOKEN "$bot_token"
    write_env_value ADMIN_CHAT_ID "$admin_chat"
    "$ROOT_DIR/scripts/install_bot.sh"
  fi

  ln -sf "$ROOT_DIR/vpn.sh" /usr/local/bin/vpn
  "$ROOT_DIR/vpn.sh" user add admin >/dev/null
  "$ROOT_DIR/scripts/install_security_hardening.sh"

  echo
  echo "=== Install complete ==="
  echo
  "$ROOT_DIR/vpn.sh" status
  echo
  echo "Admin subscription:"
  "$ROOT_DIR/vpn.sh" sub | sed -n '/admin:/p'
  echo
  echo "Files:"
  echo "  Project root: $ROOT_DIR"
  echo "  Admin bundle: $ROOT_DIR/users/admin"
  echo "  Command: /usr/local/bin/vpn"
  echo "  Public subscriptions: http://${server_host}:${port_sub}/sub/<name>"
  echo "  Admin UI tunnel: ssh -L 8081:127.0.0.1:8081 root@${server_host}"
  echo "  Then open: http://127.0.0.1:8081/  (token in $ROOT_DIR/data/server.env -> VPN_PANEL_TOKEN)"
  echo

  # Display QR codes for admin user
  if command -v qrencode >/dev/null 2>&1 && [[ -d "$ROOT_DIR/users/admin" ]]; then
    source "$ROOT_DIR/scripts/utils.sh"
    render_terminal_qrs "$ROOT_DIR" "admin"
  fi
}

main "$@"
