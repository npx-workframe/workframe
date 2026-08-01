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
# ponytail: recreate must use host-bindings overlay — /compose-relative binds
# resolve on the docker host where /compose does not exist (broken mounts).
workframe_compose_recreate up -d --force-recreate --no-deps "${SERVICES[@]}"

# nginx caches upstream IPs at startup; recreated gateway/dashboard get new IPs.
for ui_svc in workframe-ui workframe; do
  workframe_compose_recreate restart "$ui_svc" >/dev/null 2>&1 || true
done

workframe_docker_cleanup_after_update

echo "=== Hermes update complete ==="
