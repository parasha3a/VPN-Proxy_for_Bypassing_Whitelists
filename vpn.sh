#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

print_usage() {
  cat <<'EOF'
Usage:
  vpn install
  vpn user add <name>
  vpn user del <name>
  vpn user list
  vpn user info <name>
  vpn user export <name> [--zip]
  vpn sub
  vpn status
  vpn logs [service]
  vpn update
  vpn uninstall
EOF
}

run_manager() {
  "$PYTHON_BIN" "$ROOT_DIR/scripts/vpn_manager.py" "$@"
}

sync_after_user_change() {
  render_service_configs "$ROOT_DIR"
  sync_xray_service "$ROOT_DIR"
  sync_wireguard_service "$ROOT_DIR"
  sync_amneziawg_service "$ROOT_DIR"
  sync_3proxy_service "$ROOT_DIR"
}

cmd_install() {
  exec "$ROOT_DIR/install.sh"
}

cmd_user_add() {
  [[ $# -eq 1 ]] || die "usage: vpn user add <name>"
  run_manager user-add "$1"
  sync_after_user_change
  run_manager user-info "$1"
}

cmd_user_del() {
  [[ $# -eq 1 ]] || die "usage: vpn user del <name>"
  run_manager user-del "$1"
  sync_after_user_change
}

cmd_user_list() {
  run_manager user-list
}

cmd_user_info() {
  [[ $# -eq 1 ]] || die "usage: vpn user info <name>"
  run_manager user-info "$1"
  render_terminal_qrs "$ROOT_DIR" "$1"
}

cmd_user_export() {
  [[ $# -ge 1 && $# -le 2 ]] || die "usage: vpn user export <name> [--zip]"
  if [[ $# -eq 2 && "$2" != "--zip" ]]; then
    die "usage: vpn user export <name> [--zip]"
  fi
  run_manager user-export "$@"
}

cmd_sub() {
  run_manager sub-info
  echo
  echo "Service:"
  print_single_service vpn-sub.service
}

cmd_status() {
  print_status "$ROOT_DIR"
}

cmd_logs() {
  local service="${1:-}"
  print_logs "$service"
}

cmd_update() {
  "$ROOT_DIR/scripts/install_xray.sh" --upgrade
  "$ROOT_DIR/scripts/install_mtproto.sh" --upgrade
}

cmd_uninstall() {
  require_root
  uninstall_stack "$ROOT_DIR"
}

main() {
  ensure_project_layout "$ROOT_DIR"

  local cmd="${1:-}"
  shift || true

  case "$cmd" in
    install) cmd_install "$@" ;;
    user)
      local sub="${1:-}"
      shift || true
      case "$sub" in
        add) cmd_user_add "$@" ;;
        del) cmd_user_del "$@" ;;
        list) cmd_user_list "$@" ;;
        info) cmd_user_info "$@" ;;
        export) cmd_user_export "$@" ;;
        *) print_usage; exit 1 ;;
      esac
      ;;
    sub) cmd_sub "$@" ;;
    status) cmd_status "$@" ;;
    logs) cmd_logs "$@" ;;
    update) cmd_update "$@" ;;
    uninstall) cmd_uninstall "$@" ;;
    ""|-h|--help|help) print_usage ;;
    *) print_usage; exit 1 ;;
  esac
}

main "$@"
