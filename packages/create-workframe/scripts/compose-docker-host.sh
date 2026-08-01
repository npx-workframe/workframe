#!/usr/bin/env bash
# Shared docker compose invocation for in-container apply (docker.sock on host).
set -euo pipefail

# ponytail: supervisor env may omit WORKFRAME_HOST_* — install .env is canonical on VPS
_wf_export_host_paths_from_env_file() {
  local env_file="${WORKFRAME_COMPOSE_DIR:-${WORKFRAME_PROJECT_ROOT:-.}}/.env"
  [[ -f "$env_file" ]] || return 0
  if [[ -z "${WORKFRAME_HOST_COMPOSE_DIR:-}" ]]; then
    local compose_dir
    compose_dir="$(grep -m1 '^WORKFRAME_HOST_COMPOSE_DIR=' "$env_file" 2>/dev/null | cut -d= -f2- | tr -d '\r\n' || true)"
    if [[ -n "$compose_dir" ]]; then
      export WORKFRAME_HOST_COMPOSE_DIR="$compose_dir"
    fi
  fi
  if [[ -z "${WORKFRAME_HOST_PROJECT_ROOT:-}" ]]; then
    local project_root
    project_root="$(grep -m1 '^WORKFRAME_HOST_PROJECT_ROOT=' "$env_file" 2>/dev/null | cut -d= -f2- | tr -d '\r\n' || true)"
    if [[ -n "$project_root" ]]; then
      export WORKFRAME_HOST_PROJECT_ROOT="$project_root"
    fi
  fi
}

workframe_compose_prepare() {
  compose_cd=""
  compose_files=()

  _wf_export_host_paths_from_env_file

  # A supervisor invokes compose through the Docker socket. Its /compose mount is
  # the only build context it can package, so never feed the host-bindings overlay
  # back into that invocation (Windows paths become /compose/D:/... in build).
  if [[ "${WORKFRAME_UPDATE_FROM_SUPERVISOR:-}" == "1" \
        && -n "${WORKFRAME_COMPOSE_DIR:-}" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.yml" ]]; then
    compose_cd="${WORKFRAME_COMPOSE_DIR}"
    compose_files=(-f docker-compose.yml)
    if [[ -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.public.yml" ]]; then
      compose_files+=(-f docker-compose.public.yml)
    fi
    return 0
  fi

  # Host-bindings overlay: absolute WORKFRAME_HOST_* paths for docker.sock on the real host.
  # Skip inside supervisor when only the /compose bind mount is visible — host paths become
  # /compose/D:/... and break build contexts.
  if [[ -n "${WORKFRAME_HOST_COMPOSE_DIR:-}" && -n "${WORKFRAME_COMPOSE_DIR:-}" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.yml" \
        && -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.host-bindings.yml" ]]; then
    compose_cd="${WORKFRAME_COMPOSE_DIR}"
    # ponytail: docker daemon resolves WORKFRAME_HOST_* on the real host even when
    # this container only has the /compose bind (supervisor cannot stat host paths).
    compose_files=(-f docker-compose.yml -f docker-compose.host-bindings.yml)
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

workframe_compose_host_bindings_available() {
  [[ -n "${WORKFRAME_HOST_COMPOSE_DIR:-}" ]] \
    && [[ -n "${WORKFRAME_HOST_PROJECT_ROOT:-}" ]] \
    && [[ -n "${WORKFRAME_COMPOSE_DIR:-}" ]] \
    && [[ -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.host-bindings.yml" ]]
}

# ponytail: build contexts use /compose; any `up` that applies bind mounts must use host paths
workframe_compose_host_bindings() {
  if workframe_compose_host_bindings_available; then
    cd "${WORKFRAME_COMPOSE_DIR}"
    local host_files=(-f docker-compose.yml -f docker-compose.host-bindings.yml)
    if [[ -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.public.yml" ]]; then
      host_files=(-f docker-compose.yml -f docker-compose.public.yml -f docker-compose.host-bindings.yml)
    fi
    docker compose "${host_files[@]}" "$@"
    return
  fi
  workframe_compose "$@"
}

workframe_compose_recreate() {
  if workframe_compose_host_bindings_available; then
    workframe_compose_host_bindings "$@"
  else
    workframe_compose "$@"
  fi
}

workframe_compose_recreate_file_args() {
  if workframe_compose_host_bindings_available; then
    printf '%s\n' docker-compose.yml
    if [[ -f "${WORKFRAME_COMPOSE_DIR}/docker-compose.public.yml" ]]; then
      printf '%s\n' docker-compose.public.yml
    fi
    printf '%s\n' docker-compose.host-bindings.yml
    return 0
  fi
  workframe_compose_prepare
  printf '%s\n' "${compose_files[@]#-f }"
}

# After compose build/pull + recreate, drop stopped project containers and dangling images.
workframe_docker_cleanup_after_update() {
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  workframe_compose_prepare || return 0
  local project=""
  if [[ -f "${compose_cd}/docker-compose.yml" ]]; then
    cd "${compose_cd}"
    project="$(docker compose "${compose_files[@]}" config --format '{{.name}}' 2>/dev/null || true)"
  fi
  echo "=== Docker cleanup after update ==="
  if [[ -n "$project" ]]; then
    echo "Removing stopped containers for compose project: ${project}"
    docker container prune -f --filter "label=com.docker.compose.project=${project}" 2>/dev/null \
      || docker container prune -f 2>/dev/null \
      || true
  else
    docker container prune -f 2>/dev/null || true
  fi
  echo "Removing dangling images from rebuild/pull"
  docker image prune -f 2>/dev/null || true
  echo "=== Docker cleanup complete ==="
}
