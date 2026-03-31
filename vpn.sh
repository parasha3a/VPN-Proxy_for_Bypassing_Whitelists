#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
if command -v readlink >/dev/null 2>&1; then
  SCRIPT_PATH="$(readlink -f -- "$SCRIPT_PATH" 2>/dev/null || printf '%s\n' "$SCRIPT_PATH")"
fi
ROOT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"

exec "${PYTHON_BIN:-python3}" "$ROOT_DIR/scripts/vpn_manager.py" "$@"
