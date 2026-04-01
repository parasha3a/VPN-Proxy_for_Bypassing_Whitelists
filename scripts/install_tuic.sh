#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  install_singbox_binary "${1:-}"
  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services
  load_env_file "$ROOT_DIR/data/server.env"

  mkdir -p "$(dirname -- "$TUIC_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/tuic_server.json" "$TUIC_CONFIG_PATH"
  chmod 600 "$TUIC_CONFIG_PATH"

  cat >/etc/systemd/system/tuic.service <<EOF
[Unit]
Description=TUIC v5 (sing-box)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/sing-box run -c ${TUIC_CONFIG_PATH}
Restart=on-failure
RestartSec=2
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

  /usr/local/bin/sing-box check -c "$TUIC_CONFIG_PATH" >/dev/null
  systemctl daemon-reload
  systemctl enable tuic.service
  systemctl restart tuic.service
}

main "$@"
