#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"

  cat >/etc/systemd/system/vpn-bot.service <<EOF
[Unit]
Description=VPN Telegram bot
After=network.target

[Service]
WorkingDirectory=${ROOT_DIR}
ExecStart=/usr/bin/env python3 ${ROOT_DIR}/bot.py
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
ReadWritePaths=${ROOT_DIR}/data ${ROOT_DIR}/users

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable vpn-bot.service
  systemctl restart vpn-bot.service
}

main "$@"
