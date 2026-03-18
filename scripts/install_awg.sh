#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  apt-get install -y wireguard-tools || true
  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services

  mkdir -p "$(dirname -- "$AWG_SERVER_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/awg_server.conf" "$AWG_SERVER_CONFIG_PATH"
  chmod 600 "$AWG_SERVER_CONFIG_PATH"

  if command -v awg-quick >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1; then
    systemctl enable awg-quick@awg0.service || true
    systemctl restart awg-quick@awg0.service || true
  else
    echo "warning: awg-quick is not installed, awg server config was rendered only" >&2
  fi
}

main "$@"
