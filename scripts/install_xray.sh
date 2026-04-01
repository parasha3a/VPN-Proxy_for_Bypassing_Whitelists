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

parse_x25519_keys() {
  local output="$1"
  python3 - "$output" <<'PY'
import re
import sys

text = sys.argv[1]
patterns = {
    "private": [
        r"private(?:\s*|-)?key\s*[:=]\s*([A-Za-z0-9+/=_-]+)",
        r"private\s+key\s+([A-Za-z0-9+/=_-]+)",
    ],
    "public": [
        r"public(?:\s*|-)?key\s*[:=]\s*([A-Za-z0-9+/=_-]+)",
        r"public\s+key\s+([A-Za-z0-9+/=_-]+)",
    ],
}

values = {}
for kind, rules in patterns.items():
    for rule in rules:
        match = re.search(rule, text, flags=re.IGNORECASE)
        if match:
            values[kind] = match.group(1)
            break

if not values.get("private") or not values.get("public"):
    raise SystemExit(1)

print(values["private"])
print(values["public"])
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
    local key_output parsed_keys private_key public_key
    key_output="$(xray x25519)"
    if ! parsed_keys="$(parse_x25519_keys "$key_output")"; then
      die "failed to parse keys from 'xray x25519' output"
    fi
    private_key="$(sed -n '1p' <<<"$parsed_keys")"
    public_key="$(sed -n '2p' <<<"$parsed_keys")"
    [[ -n "$private_key" && -n "$public_key" ]] || die "failed to parse keys from 'xray x25519' output"
    write_env_value XRAY_REALITY_PRIVATE_KEY "$private_key"
    write_env_value XRAY_REALITY_PUBLIC_KEY "$public_key"
  fi

  python3 "$ROOT_DIR/scripts/vpn_manager.py" render-services
  load_env_file "$ROOT_DIR/data/server.env"
  mkdir -p "$(dirname -- "$XRAY_CONFIG_PATH")"
  cp "$ROOT_DIR/data/generated/xray_server.json" "$XRAY_CONFIG_PATH"
  chmod 600 "$XRAY_CONFIG_PATH"

  if ! xray run -test -config "$XRAY_CONFIG_PATH" >/dev/null 2>&1; then
    die "xray config validation failed — check $XRAY_CONFIG_PATH"
  fi

  systemctl enable xray.service
  systemctl restart xray.service
  "$ROOT_DIR/scripts/install_nginx.sh"
}

main "$@"
