#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

os_codename() {
  . /etc/os-release
  printf '%s\n' "${VERSION_CODENAME:-bookworm}"
}

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  [[ "${XRAY_WARP_ENABLE:-0}" == "1" ]] || exit 0

  install -d /usr/share/keyrings
  curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
  cat >/etc/apt/sources.list.d/cloudflare-client.list <<EOF
deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(os_codename) main
EOF

  apt-get update
  apt-get install -y cloudflare-warp
  systemctl enable --now warp-svc.service

  if ! warp-cli registration show >/dev/null 2>&1; then
    warp-cli registration new
  fi

  warp-cli mode proxy
  warp-cli proxy port "${XRAY_WARP_PORT:-40000}"
  if ! warp-cli connect >/dev/null 2>&1 && ! warp-cli status 2>/dev/null | grep -qi "connected"; then
    die "warp-cli failed to connect in proxy mode"
  fi
}

main "$@"
