#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DASH_PORT="18269"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_DASHBOARD_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then DASH_PORT="$val"; fi
fi

echo "Workframe secure setup — credentials never belong in chat."
echo ""
echo "Full Phase B (recommended): ./scripts/start-install.sh"
echo ""
echo "Hermes setup (interactive, writes to Agents/):"
echo "  docker run --rm -it --name workframe-setup --entrypoint hermes \\"
echo "    -v \"\$PWD/Agents:/opt/data\" \\"
echo "    -v \"\$PWD/Files:/workspace\" \\"
echo "    nousresearch/hermes-agent:latest setup"
echo ""
echo "Dashboard (ops UI): http://127.0.0.1:${DASH_PORT}"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:${DASH_PORT}" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:${DASH_PORT}" >/dev/null 2>&1 || true
fi
