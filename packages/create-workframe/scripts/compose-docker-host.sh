#!/usr/bin/env bash
# Shared docker compose invocation for in-container apply (docker.sock on host).
set -euo pipefail

workframe_compose_prepare() {
  compose_cd=""
  compose_files=()

  # Host-bindings overlay: absolute WORKFRAME_HOST_* paths for docker.sock on the real host.
  # Skip inside supervisor when only the /compose bind mount is visible — host paths become
  # /compose/D:/... and break build contexts.
  if [[ -n "${WORKFRAME_HOST_COMPOSE_DIR:-}" && -n "${WORKFRAME_COMPOSE_DIR:-}" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.yml" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.host-bindings.yml" ]]; then
    compose_cd="${WORKFRAME_COMPOSE_DIR}"
    if [[ -d "${WORKFRAME_HOST_COMPOSE_DIR}" ]]; then
      compose_files=(-f docker-compose.yml -f docker-compose.host-bindings.yml)
    else
      compose_files=(-f docker-compose.yml)
    fi
    return 0
  fi

  # ponytail: docker Desktop resolves WORKFRAME_HOST_* via socket even when path is not visible in this container.
  if [[ -n "${WORKFRAME_HOST_COMPOSE_DIR:-}" ]]; then
    compose_cd="${WORKFRAME_HOST_COMPOSE_DIR}"
    compose_files=(-f docker-compose.yml)
    return 0
  fi

  compose_cd="${WORKFRAME_COMPOSE_DIR:-${WORKFRAME_PROJECT_ROOT:-.}}"
  compose_files=(-f docker-compose.yml)
}

workframe_compose() {
  workframe_compose_prepare
  cd "$compose_cd"
  if [[ ! -f docker-compose.yml ]]; then
    echo "docker-compose.yml not found in $compose_cd" >&2
    exit 1
  fi
  docker compose "${compose_files[@]}" "$@"
}
