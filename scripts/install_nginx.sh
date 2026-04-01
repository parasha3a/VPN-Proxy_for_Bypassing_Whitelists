#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/utils.sh"

WEB_ROOT="/var/www/vpn-legend"
NGINX_SITE="/etc/nginx/sites-available/vpn-legend.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/vpn-legend.conf"

render_xhttp_template() {
  python3 - "$ROOT_DIR/templates/nginx_xhttp.conf" "$XRAY_CDN_DOMAIN" "$XRAY_PORT_XHTTP_CDN" "$XRAY_XHTTP_PATH" "$WEB_ROOT" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1]).read_text()
mapping = {
    "__DOMAIN__": sys.argv[2],
    "__XRAY_PORT_XHTTP_CDN__": sys.argv[3],
    "__XRAY_XHTTP_PATH__": sys.argv[4],
    "__WEB_ROOT__": sys.argv[5],
    "__CERT_PATH__": f"/etc/letsencrypt/live/{sys.argv[2]}/fullchain.pem",
    "__KEY_PATH__": f"/etc/letsencrypt/live/{sys.argv[2]}/privkey.pem",
}
for key, value in mapping.items():
    template = template.replace(key, value)
print(template)
PY
}

write_legend_page() {
  mkdir -p "$WEB_ROOT"
  cat >"$WEB_ROOT/index.html" <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Service Gateway</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e2e8f0; }
    main { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
    section { max-width: 720px; background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(148, 163, 184, 0.24); border-radius: 24px; padding: 32px; box-shadow: 0 24px 80px rgba(2, 6, 23, 0.35); }
    h1 { margin: 0 0 12px; font-size: 32px; }
    p { margin: 0 0 12px; color: #cbd5e1; line-height: 1.6; }
    .meta { margin-top: 20px; color: #94a3b8; font-size: 14px; }
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Secure Access Gateway</h1>
      <p>This endpoint serves internal traffic exchange, transport diagnostics and controlled service delivery.</p>
      <p>Public application content is intentionally minimal on this node.</p>
      <div class="meta">HTTP edge is online.</div>
    </section>
  </main>
</body>
</html>
EOF
}

write_plain_http_site() {
  cat >"$NGINX_SITE" <<EOF
server {
  listen 80 default_server;
  listen [::]:80 default_server;
  server_name _;
  root ${WEB_ROOT};
  index index.html;

  location /.well-known/acme-challenge/ {
    root ${WEB_ROOT};
  }

  location / {
    try_files \$uri /index.html;
  }
}
EOF
}

main() {
  require_root
  ensure_project_layout "$ROOT_DIR"
  load_env_file "$ROOT_DIR/data/server.env"

  apt-get install -y nginx certbot python3-certbot-nginx
  write_legend_page
  rm -f /etc/nginx/sites-enabled/default

  if [[ -n "${XRAY_CDN_DOMAIN:-}" ]]; then
    write_plain_http_site
  else
    write_plain_http_site
  fi
  ln -sf "$NGINX_SITE" "$NGINX_ENABLED"

  nginx -t
  systemctl enable nginx
  systemctl restart nginx

  if [[ -n "${XRAY_CDN_DOMAIN:-}" ]]; then
    if certbot certonly --webroot -w "$WEB_ROOT" -d "$XRAY_CDN_DOMAIN" --non-interactive --agree-tos -m "admin@${XRAY_CDN_DOMAIN}" --keep-until-expiring; then
      render_xhttp_template >"$NGINX_SITE"
      nginx -t
      systemctl restart nginx
    else
      echo "warning: certbot could not issue a certificate for ${XRAY_CDN_DOMAIN}; keeping legend-only HTTP site" >&2
    fi
  fi
}

main "$@"
