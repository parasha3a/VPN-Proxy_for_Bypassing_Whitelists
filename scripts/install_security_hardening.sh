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

unique_ports() {
  printf '%s\n' "$@" | awk 'NF && !seen[$0]++ { print $0 }'
}

configure_file_permissions() {
  secure_project_permissions "$ROOT_DIR"
}

configure_ssh() {
  local ssh_port allow_users password_only config_path ssh_service
  ssh_port="${VPN_SSH_PORT:-22}"
  allow_users="${VPN_SSH_ALLOW_USERS:-root}"
  password_only="${VPN_SSH_PASSWORD_ONLY:-1}"
  config_path="/etc/ssh/sshd_config.d/90-vpn-hardening.conf"

  mkdir -p /etc/ssh/sshd_config.d
  cat >"$config_path" <<EOF
Port ${ssh_port}
PermitRootLogin yes
PasswordAuthentication yes
KbdInteractiveAuthentication no
PermitEmptyPasswords no
X11Forwarding no
AllowAgentForwarding no
AllowStreamLocalForwarding no
AllowTcpForwarding local
GatewayPorts no
PermitTunnel no
LoginGraceTime 30
MaxAuthTries 3
MaxSessions 2
MaxStartups 10:30:60
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers ${allow_users}
UseDNS no
EOF

  if [[ "$password_only" == "1" ]]; then
    cat >>"$config_path" <<'EOF'
PubkeyAuthentication no
AuthenticationMethods password
EOF
  fi
  chmod 600 "$config_path"

  if command -v sshd >/dev/null 2>&1; then
    sshd -t -f /etc/ssh/sshd_config || die "sshd config validation failed"
  fi

  ssh_service="ssh"
  systemctl list-unit-files ssh.service >/dev/null 2>&1 || ssh_service="sshd"
  systemctl enable "$ssh_service" >/dev/null 2>&1 || true
  systemctl restart "$ssh_service"
}

configure_fail2ban() {
  [[ "${VPN_FAIL2BAN_ENABLE:-1}" == "1" ]] || return 0

  mkdir -p /etc/fail2ban/jail.d
  cat >/etc/fail2ban/jail.d/vpn-hardening.local <<EOF
[sshd]
enabled = true
port = ${VPN_SSH_PORT:-22}
backend = systemd
maxretry = 4
findtime = 10m
bantime = 1h
EOF
  chmod 600 /etc/fail2ban/jail.d/vpn-hardening.local

  systemctl enable fail2ban >/dev/null 2>&1 || true
  systemctl restart fail2ban
}

configure_firewall() {
  [[ "${VPN_FIREWALL_ENABLE:-1}" == "1" ]] || return 0

  local tcp_ports udp_ports
  tcp_ports=(
    "80"
    "${XRAY_PORT_REALITY}"
    "${XRAY_PORT_REALITY_ALT:-}"
    "${XRAY_PORT_XHTTP}"
    "${XRAY_PORT_WS}"
    "${XRAY_PORT_GRPC}"
    "${XRAY_PORT_VMESS}"
    "${SS2022_PORT:-}"
    "${HTTP_PROXY_PORT}"
    "${SOCKS5_PROXY_PORT}"
    "${SUB_PORT}"
    "${MTPROTO_PORT}"
  )
  if [[ -n "${PROXY_TLS_DOMAIN:-}" && -n "${HTTPS_PROXY_PORT:-}" ]]; then
    tcp_ports+=("${HTTPS_PROXY_PORT}")
  fi
  if [[ -n "${XRAY_CDN_DOMAIN:-}" ]]; then
    tcp_ports+=("443")
  fi
  udp_ports=(
    "${HY2_PORT}"
    "${TUIC_PORT:-}"
    "${WG_SERVER_PORT}"
  )

  ufw --force reset
  ufw default deny incoming
  ufw default allow outgoing
  ufw logging on
  ufw limit "${VPN_SSH_PORT:-22}/tcp"

  while IFS= read -r port; do
    [[ -n "$port" ]] || continue
    ufw allow "${port}/tcp"
  done < <(unique_ports "${tcp_ports[@]}")

  while IFS= read -r port; do
    [[ -n "$port" ]] || continue
    ufw allow "${port}/udp"
  done < <(unique_ports "${udp_ports[@]}")

  ufw --force enable
}

write_service_override() {
  local service="$1"
  shift
  local dir="/etc/systemd/system/${service}.d"
  mkdir -p "$dir"
  cat >"${dir}/hardening.conf"
}

configure_service_sandboxing() {
  write_service_override "xray.service" <<'EOF'
[Service]
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF

  write_service_override "hysteria.service" <<'EOF'
[Service]
UMask=0077
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF

  write_service_override "ss2022.service" <<'EOF'
[Service]
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF

  write_service_override "tuic.service" <<'EOF'
[Service]
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF

  write_service_override "3proxy.service" <<'EOF'
[Service]
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF

  if systemctl list-unit-files proxy-tls.service >/dev/null 2>&1; then
    write_service_override "proxy-tls.service" <<'EOF'
[Service]
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF
  fi

  write_service_override "mtg.service" <<'EOF'
[Service]
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
EOF

  write_service_override "vpn-sub.service" <<EOF
[Service]
UMask=0077
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
EOF

  if systemctl list-unit-files vpn-bot.service >/dev/null 2>&1; then
    write_service_override "vpn-bot.service" <<EOF
[Service]
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
EOF
  fi

  systemctl daemon-reload
  systemctl restart xray.service hysteria.service ss2022.service tuic.service 3proxy.service proxy-tls.service mtg.service vpn-sub.service >/dev/null 2>&1 || true
  systemctl restart vpn-bot.service >/dev/null 2>&1 || true
}

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  write_env_value VPN_SUB_HOST "${VPN_SUB_HOST:-0.0.0.0}"
  write_env_value VPN_ADMIN_HOST "${VPN_ADMIN_HOST:-127.0.0.1}"
  write_env_value VPN_ADMIN_PORT "${VPN_ADMIN_PORT:-8081}"
  write_env_value VPN_FIREWALL_ENABLE "${VPN_FIREWALL_ENABLE:-1}"
  write_env_value VPN_FAIL2BAN_ENABLE "${VPN_FAIL2BAN_ENABLE:-1}"
  write_env_value VPN_SSH_PORT "${VPN_SSH_PORT:-22}"
  write_env_value VPN_SSH_ALLOW_USERS "${VPN_SSH_ALLOW_USERS:-root}"
  write_env_value VPN_SSH_PASSWORD_ONLY "${VPN_SSH_PASSWORD_ONLY:-1}"
  load_env_file "$ROOT_DIR/data/server.env"

  apt-get install -y ufw fail2ban openssh-server
  configure_file_permissions
  configure_ssh
  configure_fail2ban
  configure_firewall
  configure_service_sandboxing
}

main "$@"
