#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

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
  apt-get install -y wireguard-tools
  load_env_file "$ROOT_DIR/data/server.env"

  if [[ "${WG_SERVER_PRIVATE_KEY:-CHANGE_ME}" == "CHANGE_ME" || "${WG_SERVER_PUBLIC_KEY:-CHANGE_ME}" == "CHANGE_ME" ]]; then
    local private_key public_key
    private_key="$(wg genkey)"
    public_key="$(wg pubkey <<<"$private_key")"
    write_env_value WG_SERVER_PRIVATE_KEY "$private_key"
    write_env_value WG_SERVER_PUBLIC_KEY "$public_key"
  fi

  cat >/etc/sysctl.d/99-vpn-forward.conf <<'EOF'
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
EOF
  sysctl --system >/dev/null

  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services
  load_env_file "$ROOT_DIR/data/server.env"
  mkdir -p "$(dirname -- "$WG_SERVER_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/wg_server.conf" "$WG_SERVER_CONFIG_PATH"
  chmod 600 "$WG_SERVER_CONFIG_PATH"

  systemctl enable wg-quick@wg0.service
  systemctl restart wg-quick@wg0.service
}

main "$@"
