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

  local pattern tmpdir asset tarball bin_path
  case "$(uname -m)" in
    x86_64|amd64) pattern="linux-amd64" ;;
    aarch64|arm64) pattern="linux-arm64" ;;
    *) die "unsupported architecture for mtg: $(uname -m)" ;;
  esac

  tmpdir="$(mktemp -d)"
  asset="$(github_latest_asset 9seconds/mtg "$pattern")"
  tarball="$tmpdir/mtg.tar.gz"
  download_file "$asset" "$tarball"
  tar -xzf "$tarball" -C "$tmpdir"
  bin_path="$(find "$tmpdir" -type f -name mtg | head -n 1)"
  install -m 0755 "$bin_path" /usr/local/bin/mtg

  if [[ "${MTPROTO_SECRET:-CHANGE_ME}" == "CHANGE_ME" ]]; then
    write_env_value MTPROTO_SECRET "$(mtg generate-secret "${MTPROTO_DOMAIN:-www.cloudflare.com}")"
  fi

  load_env_file "$ROOT_DIR/data/server.env"
  cat >/etc/mtg.toml <<EOF
secret = "${MTPROTO_SECRET}"
bind-to = "0.0.0.0:${MTPROTO_PORT}"
EOF

  cat >/etc/systemd/system/mtg.service <<'EOF'
[Unit]
Description=mtg - MTProto proxy
After=network.target

[Service]
ExecStart=/usr/local/bin/mtg run /etc/mtg.toml
Restart=always
RestartSec=3
DynamicUser=true
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable mtg.service
  systemctl restart mtg.service
}

main "$@"
