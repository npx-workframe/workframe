#!/usr/bin/env bash
# Shared docker compose invocation for in-container apply (docker.sock on host).
set -euo pipefail

workframe_compose_prepare() {
  compose_cd=""
  compose_files=()

  # A supervisor invokes compose through the Docker socket. Its /compose mount is
  # the only build context it can package, so never feed the host-bindings overlay
  # back into that invocation (Windows paths become /compose/D:/... in build).
  if [[ "${WORKFRAME_UPDATE_FROM_SUPERVISOR:-}" == "1" \
        && -n "${WORKFRAME_COMPOSE_DIR:-}" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.yml" ]]; then
    compose_cd="${WORKFRAME_COMPOSE_DIR}"
    compose_files=(-f docker-compose.yml)
    return 0
  fi

  # Host-bindings overlay: absolute WORKFRAME_HOST_* paths for docker.sock on the real host.
  # Skip inside supervisor when only the /compose bind mount is visible — host paths become
  # /compose/D:/... and break build contexts.
  if [[ -n "${WORKFRAME_HOST_COMPOSE_DIR:-}" && -n "${WORKFRAME_COMPOSE_DIR:-}" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.yml" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.host-bindings.yml" ]]; then
    compose_cd="${WORKFRAME_COMPOSE_DIR}"
    # Docker Desktop resolves Windows host paths via the daemon even when the
    # supervisor cannot see them as Linux directories.
    if [[ -d "${WORKFRAME_HOST_COMPOSE_DIR}" || "${WORKFRAME_HOST_COMPOSE_DIR}" =~ ^[A-Za-z]:[/\\] ]]; then
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

# Builds from inside the supervisor use /compose, but recreating a service must
# pass the generated host-bindings overlay back to Docker Desktop for its binds.
workframe_compose_host_bindings() {
  if [[ "${WORKFRAME_UPDATE_FROM_SUPERVISOR:-}" == "1" \
        && -n "${WORKFRAME_HOST_COMPOSE_DIR:-}" \
        && -n "${WORKFRAME_HOST_PROJECT_ROOT:-}" \
        && -n "${WORKFRAME_COMPOSE_DIR:-}" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.host-bindings.yml" ]]; then
    cd "${WORKFRAME_COMPOSE_DIR}"
    docker compose -f docker-compose.yml -f docker-compose.host-bindings.yml "$@"
    return
  fi
  workframe_compose "$@"
}
