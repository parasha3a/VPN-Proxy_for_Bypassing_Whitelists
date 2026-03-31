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
Description=VPN subscription and admin server
After=network.target

[Service]
WorkingDirectory=${ROOT_DIR}
Environment=VPN_SUB_HOST=${VPN_SUB_HOST:-0.0.0.0}
Environment=VPN_SUB_PORT=${SUB_PORT}
Environment=VPN_ADMIN_HOST=${VPN_ADMIN_HOST:-127.0.0.1}
Environment=VPN_ADMIN_PORT=${VPN_ADMIN_PORT:-8081}
ExecStart=/usr/bin/env python3 ${ROOT_DIR}/sub_server.py
Restart=always
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
ProtectProc=invisible
ProcSubset=pid
ReadWritePaths=${ROOT_DIR}/data ${ROOT_DIR}/users

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable vpn-sub.service
  systemctl restart vpn-sub.service
}

main "$@"
