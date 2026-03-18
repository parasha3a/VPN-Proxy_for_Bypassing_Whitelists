#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  cat >/etc/systemd/system/vpn-sub.service <<EOF
[Unit]
Description=VPN subscription server
After=network.target

[Service]
WorkingDirectory=${ROOT_DIR}
Environment=VPN_SUB_PORT=${SUB_PORT}
ExecStart=/usr/bin/env python3 ${ROOT_DIR}/sub_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable vpn-sub.service
  systemctl restart vpn-sub.service
}

main "$@"
