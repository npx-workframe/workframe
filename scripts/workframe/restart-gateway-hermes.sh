#!/usr/bin/env bash
# Restart Hermes gateway container only — no image pull. Preserves runtime/Agents.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=compose-docker-host.sh
source "$SCRIPT_DIR/compose-docker-host.sh"

echo "=== Hermes gateway restart ==="
workframe_compose_prepare
echo "Compose dir: $compose_cd"
workframe_compose up -d --force-recreate --no-deps gateway
echo "=== Gateway restart complete ==="
