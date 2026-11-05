#!/bin/sh
set -e
PORT="${PORT:-8080}"
mkdir -p /data/uploads /data/processed /data/previews /data/chroma
sed "s/__PORT__/${PORT}/" /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
exec nginx -g "daemon off;"
