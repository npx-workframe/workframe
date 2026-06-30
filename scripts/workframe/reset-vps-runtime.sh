#!/usr/bin/env bash
# Wipe VPS Workframe runtime only — preserves source tree and infra/compose/workframe/.env.
# Fresh install window; do not use repair-install-complete.mjs for E2E after this.
set -euo pipefail

ROOT="${WORKFRAME_REPO_ROOT:-/opt/workframe/repo}"
COMPOSE_DIR="$ROOT/infra/compose/workframe"

[[ -d "$ROOT" ]] || { echo "missing project root: $ROOT"; exit 1; }

echo "=== VPS runtime wipe (slot preserved via .env) ==="
cd "$COMPOSE_DIR"
docker compose down --remove-orphans || true

for sub in Agents Files workframe-api-data; do
  rm -rf "$ROOT/runtime/$sub"
done
mkdir -p "$ROOT/runtime/Agents/profiles" "$ROOT/runtime/Files" "$ROOT/runtime/workframe-api-data"
chmod -R a+rwX "$ROOT/runtime/Agents" "$ROOT/runtime/Files" "$ROOT/runtime/workframe-api-data" 2>/dev/null || true

echo "=== bootstrap workframe-agent ==="
bash "$ROOT/scripts/workframe/bootstrap-native.sh"

echo "=== docker compose up (rebuild API/supervisor, build UI on server) ==="
bash "$ROOT/scripts/workframe/vps-deploy.sh"

API_PORT=$(grep -E '^WORKFRAME_API_PORT=' "$COMPOSE_DIR/.env" 2>/dev/null | cut -d= -f2 || echo 29120)
UI_PORT=$(grep -E '^WORKFRAME_UI_PORT=' "$COMPOSE_DIR/.env" 2>/dev/null | cut -d= -f2 || echo 28644)
echo ""
echo "Fresh VPS runtime ready:"
echo "  UI  http://127.0.0.1:${UI_PORT}/"
echo "  API http://127.0.0.1:${API_PORT}/api/install/status"
echo ""
curl -s "http://127.0.0.1:${API_PORT}/api/install/status"
echo
