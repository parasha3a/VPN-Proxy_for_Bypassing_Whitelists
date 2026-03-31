#!/usr/bin/env bash
set -euo pipefail

# Персистентные sysctl для пропускной способности VPN (безопасные значения по умолчанию).
SYSCTL_FILE="/etc/sysctl.d/99-vpn-deploy.conf"

write_base() {
  cat >"$SYSCTL_FILE" <<'EOF'
# vpn-deploy: network tuning (safe defaults)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
fs.file-max = 1048576
EOF
}

append_bbr_if_available() {
  if [[ ! -f /proc/sys/net/ipv4/tcp_congestion_control ]]; then
    return 0
  fi
  if ! grep -q '^tcp_bbr' /proc/modules 2>/dev/null; then
    modprobe tcp_bbr 2>/dev/null || return 0
  fi
  cat >>"$SYSCTL_FILE" <<'EOF'
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
}

write_base
append_bbr_if_available

if command -v sysctl >/dev/null 2>&1; then
  sysctl --system >/dev/null 2>&1 || sysctl -p "$SYSCTL_FILE" >/dev/null 2>&1 || true
fi

echo "[network-tuning] wrote $SYSCTL_FILE"
