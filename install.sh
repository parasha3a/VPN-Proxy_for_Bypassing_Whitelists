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
  curl -fsSL https://api.ipify.org || hostname -I | awk '{print $1}'
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

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"

  if [[ ! -f /etc/debian_version ]]; then
    die "supported OS: Ubuntu 22.04+ or Debian 12+"
  fi

  banner
  local public_ip
  public_ip="$(detect_public_ip)"
  echo "Detected public IP: $public_ip"

  local server_name server_host install_wg install_bot
  server_name="$(prompt_default "Server name" "MyVPN")"
  server_host="$(prompt_default "Share host/IP" "$public_ip")"
  install_wg="N"
  install_bot="N"
  yes_no "Install plain WireGuard too?" "n" && install_wg="Y"
  yes_no "Install Telegram bot?" "n" && install_bot="Y"

  write_env_value SERVER_NAME "$server_name"
  write_env_value SERVER_IP "$public_ip"
  write_env_value SERVER_HOST "$server_host"

  echo
  echo "[x] Xray-core (VLESS Reality + XHTTP + WS + gRPC + VMess)"
  echo "[x] AmneziaWG"
  if [[ "$install_wg" == "Y" ]]; then echo "[x] WireGuard plain"; else echo "[ ] WireGuard plain"; fi
  echo "[x] HTTP + SOCKS5 proxy (3proxy)"
  echo "[x] MTProto (mtg)"
  echo "[x] Subscription server"
  if [[ "$install_bot" == "Y" ]]; then echo "[x] Telegram bot"; else echo "[ ] Telegram bot"; fi
  echo

  apt-get update
  apt-get install -y curl wget unzip tar ca-certificates python3 python3-venv jq qrencode uuid-runtime iproute2 iptables

  "$ROOT_DIR/scripts/install_xray.sh"
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

  echo
  echo "Install complete."
  "$ROOT_DIR/vpn.sh" status
  echo
  echo "Admin subscription:"
  "$ROOT_DIR/vpn.sh" sub | sed -n '/admin:/p'
  echo
  echo "Files:"
  echo "  Project root: $ROOT_DIR"
  echo "  Admin bundle: $ROOT_DIR/users/admin"
  echo "  Command: /usr/local/bin/vpn"
}

main "$@"
