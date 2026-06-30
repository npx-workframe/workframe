#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MISSION_PORT=""
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_MISSION_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then MISSION_PORT="$val"; fi
fi

if [ -z "$MISSION_PORT" ]; then
  echo "Mission control is deprecated and not enabled in the default Workframe stack."
  echo "Use Workframe UI or Workframe API instead."
  exit 0
fi

URL="http://127.0.0.1:${MISSION_PORT}/"
echo "Opening Workframe mission control: $URL"
for _ in $(seq 1 22); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null; then break; fi
  sleep 2
done
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 || true
else echo "Open manually: $URL"
fi
