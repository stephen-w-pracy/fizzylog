#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/root/fizzylog"
BACKEND_DIR="${REPO_ROOT}/backend"
FRONTEND_DIR="${REPO_ROOT}/frontend"
VENV_DIR="/opt/fizzylog/venv"
CONFIG_PATH="/etc/fizzylog/config.yml"

export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y nginx python3 python3-venv python3-pip sqlite3 rsync

mkdir -p /opt/fizzylog /etc/fizzylog /var/lib/fizzylog /var/www/fizzylog

if [ ! -d "${VENV_DIR}" ]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"

if [ ! -f "${CONFIG_PATH}" ]; then
  cat > "${CONFIG_PATH}" <<'EOF'
log:
  path: /var/log/nginx/access.log
  format: nginx_combined

window:
  lookback_seconds: 21600
  bucket_seconds: 60

paths:
  include_exact:
    - /
    - /terms.html
  aliases:
    /index.html: /
  strip_query_string: true
  ignore_static_assets: true

status_filter:
  default_mode: ranges
  default_ranges: [2xx, 3xx]

ui:
  refresh_seconds: 2
  max_points: 360

storage:
  backend: sqlite
  sqlite_path: /var/lib/fizzylog/rollups.sqlite
  retention_seconds: 43200

ingest:
  flush_seconds: 2
EOF
fi

cat > /etc/systemd/system/fizzylog.service <<EOF
[Unit]
Description=fizzylog
After=network.target nginx.service

[Service]
Type=simple
WorkingDirectory=${BACKEND_DIR}
ExecStart=${VENV_DIR}/bin/python -m fizzylog.main --config ${CONFIG_PATH}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

rsync -a --delete "${FRONTEND_DIR}/" /var/www/fizzylog/

cat > /etc/nginx/sites-available/fizzylog <<'EOF'
server {
    listen 80;
    server_name _;

    root /var/www/fizzylog;
    index index.html;
    access_log /var/log/nginx/fizzylog.access.log;
    error_log /var/log/nginx/fizzylog.error.log;

    location / {
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/fizzylog /etc/nginx/sites-enabled/fizzylog

nginx -t
systemctl daemon-reload
systemctl enable fizzylog.service
systemctl restart nginx
systemctl restart fizzylog.service
