#!/usr/bin/env bash
# Install Caddy on the VPS host and reverse-proxy HTTPS -> Workframe UI loopback port.
# Usage: sudo bash scripts/workframe/setup-public-https.sh dev.example.com 28644
set -euo pipefail

HOST="${1:?domain required (e.g. dev.example.com)}"
PORT="${2:-28644}"
HOST="${HOST#https://}"
HOST="${HOST#http://}"
HOST="${HOST%%/*}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on the VPS: sudo bash $0 $HOST $PORT" >&2
  exit 1
fi

if ! command -v caddy >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq
  apt-get install -y caddy
fi

cat > /etc/caddy/Caddyfile <<EOF
${HOST} {
  reverse_proxy 127.0.0.1:${PORT}
}
EOF

systemctl enable caddy
systemctl reload caddy 2>/dev/null || systemctl restart caddy

echo "OK — https://${HOST} -> 127.0.0.1:${PORT}"
echo "Ensure DNS A record points here and ports 80/443 are open, then test: curl -sI https://${HOST}/api/health"
