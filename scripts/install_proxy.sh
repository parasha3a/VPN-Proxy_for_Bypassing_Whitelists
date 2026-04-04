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

looks_like_hostname() {
  python3 - "$1" <<'PY'
import ipaddress
import re
import sys

value = sys.argv[1].strip()
if not value or re.search(r"\s", value):
    raise SystemExit(1)
try:
    ipaddress.ip_address(value)
except ValueError:
    if "." in value and re.fullmatch(r"[A-Za-z0-9.-]+", value):
        raise SystemExit(0)
raise SystemExit(1)
PY
}

disable_proxy_tls() {
  write_env_value PROXY_TLS_READY "0"
  systemctl disable --now proxy-tls.service 2>/dev/null || true
  rm -f /etc/systemd/system/proxy-tls.service
  [[ -n "${PROXY_TLS_CONFIG_PATH:-}" ]] && rm -f "$PROXY_TLS_CONFIG_PATH"
  systemctl daemon-reload >/dev/null 2>&1 || true
}

ensure_proxy_tls_defaults() {
  if [[ -z "${PROXY_TLS_DOMAIN:-}" && -n "${SERVER_HOST:-}" ]] && looks_like_hostname "$SERVER_HOST"; then
    write_env_value PROXY_TLS_DOMAIN "$SERVER_HOST"
  fi
  load_env_file "$ROOT_DIR/data/server.env"

  if [[ -n "${PROXY_TLS_DOMAIN:-}" && -z "${PROXY_TLS_CERT_PATH:-}" ]]; then
    write_env_value PROXY_TLS_CERT_PATH "/etc/letsencrypt/live/${PROXY_TLS_DOMAIN}/fullchain.pem"
  fi
  if [[ -n "${PROXY_TLS_DOMAIN:-}" && -z "${PROXY_TLS_KEY_PATH:-}" ]]; then
    write_env_value PROXY_TLS_KEY_PATH "/etc/letsencrypt/live/${PROXY_TLS_DOMAIN}/privkey.pem"
  fi
  if [[ -z "${PROXY_TLS_CONFIG_PATH:-}" ]]; then
    write_env_value PROXY_TLS_CONFIG_PATH "/etc/stunnel/https-proxy.conf"
  fi
}

configure_proxy_tls() {
  if [[ -z "${PROXY_TLS_DOMAIN:-}" ]]; then
    disable_proxy_tls
    return 0
  fi
  if ! looks_like_hostname "$PROXY_TLS_DOMAIN"; then
    echo "warning: PROXY_TLS_DOMAIN must be a hostname, got '${PROXY_TLS_DOMAIN}'; skipping HTTPS proxy" >&2
    disable_proxy_tls
    return 0
  fi
  if [[ ! -d /var/www/vpn-legend ]]; then
    echo "warning: nginx webroot /var/www/vpn-legend is missing; skipping HTTPS proxy" >&2
    disable_proxy_tls
    return 0
  fi

  apt-get install -y stunnel4 certbot >/dev/null

  local cert_path key_path config_path
  cert_path="${PROXY_TLS_CERT_PATH:-/etc/letsencrypt/live/${PROXY_TLS_DOMAIN}/fullchain.pem}"
  key_path="${PROXY_TLS_KEY_PATH:-/etc/letsencrypt/live/${PROXY_TLS_DOMAIN}/privkey.pem}"
  config_path="${PROXY_TLS_CONFIG_PATH:-/etc/stunnel/https-proxy.conf}"

  if ! certbot certonly --webroot -w /var/www/vpn-legend -d "$PROXY_TLS_DOMAIN" --non-interactive --agree-tos -m "admin@${PROXY_TLS_DOMAIN}" --keep-until-expiring; then
    echo "warning: certbot could not issue a certificate for ${PROXY_TLS_DOMAIN}; HTTPS proxy remains disabled" >&2
    disable_proxy_tls
    return 0
  fi

  write_env_value PROXY_TLS_CERT_PATH "$cert_path"
  write_env_value PROXY_TLS_KEY_PATH "$key_path"
  write_env_value PROXY_TLS_CONFIG_PATH "$config_path"

  mkdir -p "$(dirname -- "$config_path")"
  cat >"$config_path" <<EOF
foreground = yes
setuid = stunnel4
setgid = stunnel4
pid =
client = no
socket = l:TCP_NODELAY=1
socket = r:TCP_NODELAY=1

[https-proxy]
accept = 0.0.0.0:${HTTPS_PROXY_PORT}
connect = 127.0.0.1:${HTTP_PROXY_PORT}
cert = ${cert_path}
key = ${key_path}
TIMEOUTclose = 0
EOF
  chmod 600 "$config_path"

  local stunnel_bin
  stunnel_bin="$(command -v stunnel4 || command -v stunnel || true)"
  [[ -n "$stunnel_bin" ]] || die "stunnel binary not found after installation"

  cat >/etc/systemd/system/proxy-tls.service <<EOF
[Unit]
Description=HTTPS proxy TLS wrapper
After=network.target 3proxy.service
Wants=3proxy.service

[Service]
Type=simple
ExecStart=${stunnel_bin} ${config_path}
Restart=always
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable proxy-tls.service
  systemctl restart proxy-tls.service
  write_env_value PROXY_TLS_READY "1"
}

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"
  ensure_proxy_tls_defaults
  load_env_file "$ROOT_DIR/data/server.env"

  if ! apt-get install -y 3proxy stunnel4; then
    local pattern tmpdir asset pkg
    case "$(dpkg --print-architecture 2>/dev/null || uname -m)" in
      amd64|x86_64) pattern=".x86_64.deb" ;;
      arm64|aarch64) pattern=".aarch64.deb" ;;
      armhf|armv7l) pattern=".arm.deb" ;;
      *) die "unsupported architecture for 3proxy fallback: $(uname -m)" ;;
    esac

    tmpdir="$(mktemp -d)"
    asset="$(github_latest_asset 3proxy/3proxy "$pattern")"
    pkg="$tmpdir/3proxy.deb"
    download_file "$asset" "$pkg"
    apt-get install -y "$pkg" || {
      dpkg -i "$pkg" || true
      apt-get install -fy
      dpkg -i "$pkg"
    }
  fi
  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services

  mkdir -p "$(dirname -- "$THREEPROXY_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/3proxy.cfg" "$THREEPROXY_CONFIG_PATH"
  chmod 600 "$THREEPROXY_CONFIG_PATH"

  local threeproxy_bin
  threeproxy_bin="$(command -v 3proxy)"
  cat >/etc/systemd/system/3proxy.service <<EOF
[Unit]
Description=3proxy tiny proxy server
After=network.target

[Service]
Type=forking
ExecStart=${threeproxy_bin} ${THREEPROXY_CONFIG_PATH}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable 3proxy.service
  systemctl restart 3proxy.service
  configure_proxy_tls
  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-users
}

main "$@"
