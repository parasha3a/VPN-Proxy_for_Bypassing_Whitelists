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

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  if [[ ! -x /usr/local/bin/xray || "${1:-}" == "--upgrade" ]]; then
    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
  fi

  if [[ "${XRAY_REALITY_PRIVATE_KEY:-CHANGE_ME}" == "CHANGE_ME" || "${XRAY_REALITY_PUBLIC_KEY:-CHANGE_ME}" == "CHANGE_ME" ]]; then
    local key_output private_key public_key
    key_output="$(xray x25519)"
    private_key="$(awk -F': ' '/Private key/ {print $2}' <<<"$key_output")"
    public_key="$(awk -F': ' '/Public key/ {print $2}' <<<"$key_output")"
    write_env_value XRAY_REALITY_PRIVATE_KEY "$private_key"
    write_env_value XRAY_REALITY_PUBLIC_KEY "$public_key"
  fi

  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services
  load_env_file "$ROOT_DIR/data/server.env"
  mkdir -p "$(dirname -- "$XRAY_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/xray_server.json" "$XRAY_CONFIG_PATH"

  systemctl enable xray.service
  systemctl restart xray.service
}

main "$@"
