#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UI_PORT="18644"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_UI_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then UI_PORT="$val"; fi
fi

echo "Starting Workframe stack (if needed)..."
docker compose up -d

URL="http://127.0.0.1:${UI_PORT}/"
echo "Opening Workframe UI: $URL"
for _ in $(seq 1 45); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null && curl -fsS "$URL/api/hermes/bootstrap" 2>/dev/null | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    break
  fi
  sleep 2
done
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
else
  echo "Open manually: $URL"
fi
