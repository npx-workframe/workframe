#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f "$ROOT/Agents/config.yaml" ]; then
  echo "Hermes is not initialized in Agents/." >&2
  echo "Run: ./scripts/start-install.sh" >&2
  exit 1
fi

echo "Bootstrapping Workframe Agent (workframe-agent)..."
"$ROOT/scripts/bootstrap-native.sh"
"$ROOT/scripts/verify-bootstrap.sh"

echo "Starting full stack (gateway, dashboard, workframe-api, Workframe UI)..."
docker compose up -d

echo ""
echo "Phase B complete — Workframe Agent is ready."
echo "  Browser chat (TUI): http://127.0.0.1:18269/chat"
echo "  Terminal chat: ./scripts/chat.sh"
echo "  Auth/UI surface: http://127.0.0.1:18644"
echo "  Workframe UI: http://127.0.0.1:18270"
echo "  Hermes ops dashboard: http://127.0.0.1:18269"
echo "  Add specialists: ./scripts/add-profile.sh <slug>"
echo ""
echo "Opening Workframe UI..."
"$ROOT/scripts/open-workframe-ui.sh" || true

