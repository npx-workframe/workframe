#!/usr/bin/env bash
# Safe Hermes update — pull gateway/dashboard images, recreate containers. Preserves runtime/Agents.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=compose-docker-host.sh
source "$SCRIPT_DIR/compose-docker-host.sh"

echo "=== Hermes update (gateway + dashboard only) ==="
workframe_compose_prepare
echo "Compose dir: $compose_cd"
echo "Preserves: Agents/, Files/, workframe-api data volumes"

SERVICES=(gateway dashboard)
workframe_compose pull "${SERVICES[@]}"
workframe_compose up -d --force-recreate --no-deps "${SERVICES[@]}"

echo "=== Hermes update complete ==="
