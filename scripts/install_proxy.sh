#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  apt-get install -y 3proxy
  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services

  mkdir -p "$(dirname -- "$THREEPROXY_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/3proxy.cfg" "$THREEPROXY_CONFIG_PATH"

  local threeproxy_bin
  threeproxy_bin="$(command -v 3proxy)"
  cat >/etc/systemd/system/3proxy.service <<EOF
[Unit]
Description=3proxy tiny proxy server
After=network.target

[Service]
ExecStart=${threeproxy_bin} ${THREEPROXY_CONFIG_PATH}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable 3proxy.service
  systemctl restart 3proxy.service
}

main "$@"
