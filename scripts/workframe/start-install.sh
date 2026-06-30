#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p Agents Files

echo ""
echo "========================================"
echo " Workframe Phase B - complete boot"
echo " Project: Workframe Agent"
echo "========================================"
echo ""
echo "Step 1/3 - Hermes setup (credentials, interactive)"
echo ""

docker pull nousresearch/hermes-agent:latest
docker run --rm -it --name workframe-setup --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest setup
setup_code=$?
if [ "$setup_code" -ne 0 ]; then
  echo "Hermes setup cancelled or failed."
  read -r -p "Press Enter to close..." _
  exit "$setup_code"
fi

echo ""
echo "Step 2/3 - Bootstrap Workframe Agent..."
"$ROOT/scripts/bootstrap-native.sh"
"$ROOT/scripts/verify-bootstrap.sh"

echo ""
echo "Step 3/3 - Full stack (gateway, dashboard, workframe-api, Workframe UI)..."
docker compose up -d

echo ""
echo "========================================"
echo " Phase B complete - Workframe Agent is ready"
echo "========================================"
echo ""
echo "  Browser chat (TUI): http://127.0.0.1:18269/chat"
echo "  Terminal chat:     ./scripts/chat.sh"
echo "  Auth/UI surface:   http://127.0.0.1:18644"
echo "  Workframe UI:      http://127.0.0.1:18270"
echo "  Hermes ops:        http://127.0.0.1:18269"
echo ""
echo "Opening Workframe UI..."
"$ROOT/scripts/open-workframe-ui.sh" || true

read -r -p "Press Enter to close..." _
