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

  mkdir -p "$(dirname -- "$SS2022_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/ss2022_server.json" "$SS2022_CONFIG_PATH"
  chmod 600 "$SS2022_CONFIG_PATH"

  cat >/etc/systemd/system/ss2022.service <<EOF
[Unit]
Description=Shadowsocks 2022 (sing-box)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/sing-box run -c ${SS2022_CONFIG_PATH}
Restart=on-failure
RestartSec=2
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

  /usr/local/bin/sing-box check -c "$SS2022_CONFIG_PATH" >/dev/null
  systemctl daemon-reload
  systemctl enable ss2022.service
  systemctl restart ss2022.service
}

main "$@"
