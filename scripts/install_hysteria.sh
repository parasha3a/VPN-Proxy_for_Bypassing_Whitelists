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

download_hysteria() {
  local dst="$1"
  local arch url
  case "$(uname -m)" in
    x86_64|amd64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) die "unsupported architecture for hysteria: $(uname -m)" ;;
  esac
  url="https://download.hysteria.network/app/latest/hysteria-linux-${arch}"
  curl -fsSL "$url" -o "$dst"
}

ensure_cert() {
  local host="$1"
  local ip="$2"
  local cert_path="$3"
  local key_path="$4"
  mkdir -p "$(dirname -- "$cert_path")"

  if [[ -f "$cert_path" && -f "$key_path" ]]; then
    return 0
  fi

  local san
  if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    san="IP:${host},IP:${ip}"
  else
    san="DNS:${host},IP:${ip}"
  fi

  openssl req -x509 -newkey rsa:2048 -sha256 -nodes \
    -keyout "$key_path" \
    -out "$cert_path" \
    -days 3650 \
    -subj "/CN=${host}" \
    -addext "subjectAltName = ${san}" >/dev/null 2>&1
}

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  local tmp_bin
  tmp_bin="$(mktemp)"
  trap 'rm -f "$tmp_bin"' EXIT
  download_hysteria "$tmp_bin"
  install -m 0755 "$tmp_bin" /usr/local/bin/hysteria

  if [[ "${HY2_OBFS_PASSWORD:-CHANGE_ME}" == "CHANGE_ME" ]]; then
    write_env_value HY2_OBFS_PASSWORD "$(openssl rand -hex 16)"
  fi

  ensure_cert "${HY2_TLS_SNI:-$SERVER_HOST}" "${SERVER_IP:-127.0.0.1}" "${HY2_CERT_PATH}" "${HY2_KEY_PATH}"
  write_env_value HY2_PIN_SHA256 "$(openssl x509 -in "$HY2_CERT_PATH" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')"

  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services
  load_env_file "$ROOT_DIR/data/server.env"
  mkdir -p "$(dirname -- "$HY2_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/hysteria_server.yaml" "$HY2_CONFIG_PATH"
  chmod 600 "$HY2_CONFIG_PATH" "$HY2_CERT_PATH" "$HY2_KEY_PATH"

  cat >/etc/systemd/system/hysteria.service <<EOF
[Unit]
Description=Hysteria2 server
After=network.target

[Service]
ExecStart=/usr/local/bin/hysteria server -c ${HY2_CONFIG_PATH}
Restart=always
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable hysteria.service
  systemctl restart hysteria.service
}

main "$@"
