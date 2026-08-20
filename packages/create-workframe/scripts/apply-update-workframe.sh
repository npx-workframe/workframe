#!/usr/bin/env bash
# Safe Workframe update — sync npm template (optional), rebuild API/supervisor/UI containers. Never wipes runtime/DB.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=compose-docker-host.sh
source "$SCRIPT_DIR/compose-docker-host.sh"

# ponytail: npm integrity via python3 — Alpine supervisor has no xxd
_wf_prefetched_integrity_ok() {
  local tarball="$1" manifest="${1}.sha512"
  local expected actual
  if [[ ! -s "$manifest" ]]; then
    echo "prefetched tarball integrity manifest is missing: $manifest" >&2
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to verify the prefetched update tarball" >&2
    return 1
  fi
  expected="$(tr -d '\r\n' < "$manifest")"
  actual="$(python3 -c 'import base64, hashlib, sys
p = sys.argv[1]
d = hashlib.sha512(open(p, "rb").read()).digest()
print("sha512-" + base64.b64encode(d).decode())' "$tarball")"
  [[ "$actual" == "$expected" ]]
}

# Host path in .env may not exist inside supervisor — use compose mount when it does not.
_wf_resolve_project_root() {
  local host="${WORKFRAME_HOST_PROJECT_ROOT:-}"
  local proj="${WORKFRAME_PROJECT_ROOT:-}"
  if [[ -n "$host" && -d "$host" ]]; then
    printf '%s' "$host"
    return
  fi
  if [[ -n "$host" ]]; then
    printf '%s' "$compose_cd"
    return
  fi
  printf '%s' "${proj:-$compose_cd}"
}

_wf_sync_tree() {
  local src="$1" dest="$2"
  mkdir -p "$dest"
  cp -a "${src}/." "${dest}/"
}

_wf_validate_ui_tree() {
  local root="$1" index="$1/index.html" ref rel
  [[ -f "$index" ]] || { echo "ERROR: staged UI index missing: $index" >&2; return 1; }
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    rel="${ref#./}"
    rel="${rel#/}"
    if [[ ! -f "$root/$rel" ]]; then
      echo "ERROR: staged UI index references missing asset: $ref" >&2
      return 1
    fi
  done < <(grep -oE '(src|href)="(\./|/)assets/[^"?]+' "$index" | sed -E 's/^[^=]+="//')
}

_wf_sync_from_pack_dir() {
  local pkg="$1"
  if [[ -d "$pkg/workframe-api" ]]; then
    echo "Syncing workframe-api -> $API_DIR"
    _wf_sync_tree "$pkg/workframe-api" "$API_DIR"
  fi
  if [[ -d "$pkg/workframe-supervisor" ]]; then
    echo "Syncing workframe-supervisor -> $SUP_DIR"
    _wf_sync_tree "$pkg/workframe-supervisor" "$SUP_DIR"
  fi
  if [[ -d "$pkg/workframe-ui/public" ]]; then
    WF_UPDATE_UI_SRC="$pkg/workframe-ui/public"
  fi
  if [[ -f "$pkg/workframe-ui/docker/nginx.conf" ]]; then
    WF_UPDATE_NGINX_SRC="$pkg/workframe-ui/docker/nginx.conf"
  fi
  if [[ -d "$pkg/scripts" ]]; then
    for script in "$pkg/scripts"/*.sh; do
      [[ -f "$script" ]] || continue
      cp -a "$script" "$SCRIPTS_DIR/$(basename "$script")"
      chmod +x "$SCRIPTS_DIR/$(basename "$script")" 2>/dev/null || true
    done
  fi
}

_wf_apply_npm_tarball() {
  local tarball="$1"
  local ver="${2:-latest}"
  local source="${3:-npm}"
  if [[ "$source" == "prefetched" ]] && ! _wf_prefetched_integrity_ok "$tarball"; then
    echo "integrity mismatch for API-prefetched ${NPM_PACKAGE}@${ver}" >&2
    exit 1
  fi
  echo "integrity verified: ${NPM_PACKAGE}@${ver} ($source)"
  local extract_dir
  extract_dir="$(mktemp -d)"
  tar -xf "$tarball" -C "$extract_dir"
  WF_UPDATE_EXTRACT_DIR="$extract_dir"
  _wf_sync_from_pack_dir "$extract_dir/package"
}

_wf_record_package_version() {
  local ver="$1"
  [[ -n "$ver" ]] || return 0
  mkdir -p "$API_DIR/data"
  printf '%s\n' "$ver" > "$API_DIR/data/package-version"
  if [[ -f "$PROJECT_ROOT/workframe-manifest.json" ]] && command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json, sys
from pathlib import Path
p = Path(sys.argv[1])
ver = sys.argv[2]
data = json.loads(p.read_text(encoding="utf-8"))
data["package_version"] = ver
data["generator"] = f"create-workframe@{ver}"
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")' "$PROJECT_ROOT/workframe-manifest.json" "$ver"
  fi
}

_wf_commit_compose_alignment() {
  local ver="$1"
  [[ -n "$ver" ]] || return 0
  _wf_sync_env_api_version "$ver"
  _wf_sync_compose_api_version "$ver"
}

_wf_commit_version_alignment() {
  local ver="$1"
  _wf_commit_compose_alignment "$ver"
  _wf_record_package_version "$ver"
}

_wf_read_stamp_version() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  python3 -c 'import json, sys
from pathlib import Path
p = Path(sys.argv[1])
try:
    data = json.loads(p.read_text(encoding="utf-8"))
except Exception:
    sys.exit(0)
print(str(data.get("package_version") or "").strip())' "$file" 2>/dev/null || true
}

_wf_verify_version_alignment() {
  local ver="$1"
  [[ -n "$ver" ]] || return 0
  local pin api_build ui_build supervisor_build env_ver compose_ver running_ver
  pin="$(tr -d '\r\n' < "$API_DIR/data/package-version" 2>/dev/null || true)"
  api_build="$(_wf_read_stamp_version "$API_DIR/workframe-api-build.json")"
  ui_build="$(_wf_read_stamp_version "$UI_DIR/workframe-build.json")"
  supervisor_build="$(_wf_read_stamp_version "$SUP_DIR/workframe-supervisor-build.json")"
  env_ver="$(grep '^WORKFRAME_API_VERSION=' "$compose_cd/.env" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '\r\n' || true)"
  compose_ver="$(grep -E '^[[:space:]]*- WORKFRAME_API_VERSION=' "$compose_cd/docker-compose.yml" 2>/dev/null | tail -n1 | sed -E 's/^[[:space:]]*- WORKFRAME_API_VERSION=//' | tr -d '\r\n' || true)"
  local mismatch=0
  for label in api_build:api-build ui_build:ui-build supervisor_build:supervisor-build env_ver:.env compose_ver:compose; do
    local name="${label%%:*}"
    local value="${!name}"
    if [[ -n "$value" && "$value" != "$ver" ]]; then
      echo "ERROR: ${label#*:} is v${value} but target is v${ver}" >&2
      mismatch=1
    fi
  done
  if [[ "$mismatch" -ne 0 ]]; then
    exit 1
  fi
  local attempt state running_ver
  for attempt in $(seq 1 90); do
    state="$(workframe_compose_recreate ps workframe-api 2>/dev/null | tail -n +2 | awk '{print $NF}' | head -n1 || true)"
    if [[ "$state" == Restarting* ]]; then
      sleep 2
      continue
    fi
    running_ver="$(workframe_compose_recreate exec -T workframe-api printenv WORKFRAME_API_VERSION 2>/dev/null | tr -d '\r\n' || true)"
    if [[ "$running_ver" == "$ver" ]]; then
      echo "Version alignment verified: v${ver} (files + running API)"
      return 0
    fi
    sleep 2
  done
  echo "ERROR: running API WORKFRAME_API_VERSION=${running_ver:-<unset>} expected v${ver}" >&2
  exit 1
}

# ponytail: sibling container restarts supervisor — never docker-compose self from inside self
_wf_schedule_supervisor_restart() {
  workframe_compose_prepare
  local delay="${WORKFRAME_SUPERVISOR_RESTART_DELAY:-15}"
  local self_image=""
  if command -v docker >/dev/null 2>&1; then
    self_image="$(docker inspect --format '{{.Config.Image}}' "$(hostname)" 2>/dev/null || true)"
  fi
  if [[ -z "$self_image" ]]; then
    self_image="$(workframe_compose images -q workframe-supervisor 2>/dev/null | head -n1 || true)"
  fi
  if [[ -z "$self_image" ]]; then
    echo "WARN: could not resolve supervisor image — skipping deferred supervisor restart" >&2
    return 0
  fi
  local host_cd="${WORKFRAME_HOST_COMPOSE_DIR:-$compose_cd}"
  local host_root="${WORKFRAME_HOST_PROJECT_ROOT:-$host_cd}"
  local scripts_rel="scripts"
  if [[ "$SCRIPTS_DIR" == "$PROJECT_ROOT/"* ]]; then
    scripts_rel="${SCRIPTS_DIR#"$PROJECT_ROOT/"}"
  fi
  local host_scripts="${host_root}/${scripts_rel}"
  host_scripts="${host_scripts//\\//}"
  local sibling_cd="/workframe-host"
  local restart_overlay="${compose_cd}/.workframe-supervisor-restart.yml"
  local host_scripts_yaml="${host_scripts//\"/\\\"}"
  cat > "$restart_overlay" <<EOF
services:
  workframe-supervisor:
    volumes:
      - type: bind
        source: "${host_scripts_yaml}"
        target: /opt/install/scripts
        read_only: true
EOF
  local compose_cmd="docker compose"
  local compose_file
  while IFS= read -r compose_file; do
    [[ -n "$compose_file" ]] || continue
    compose_cmd+=" $(printf '%q' "$compose_file")"
  done < <(workframe_compose_recreate_file_args)
  compose_cmd+=" -f .workframe-supervisor-restart.yml"
  local job_name="wf-sup-restart-$$"
  echo "Scheduling supervisor restart via sibling container in ${delay}s (${job_name})"
  # Retry with an explicit rm if the recreate leaves a Created-state corpse.
  docker run -d --rm \
    --name "$job_name" \
    --env-file "${compose_cd}/.env" \
    -e "WORKFRAME_HOST_COMPOSE_DIR=${host_cd}" \
    -e "WORKFRAME_HOST_PROJECT_ROOT=${host_root}" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${host_cd}:${sibling_cd}" \
    -w "${sibling_cd}" \
    "$self_image" \
    sh -lc "trap 'rm -f .workframe-supervisor-restart.yml' EXIT; sleep ${delay}; \
(${compose_cmd} up -d --no-build --no-deps --force-recreate workframe-supervisor \
|| { ${compose_cmd} rm -sf workframe-supervisor; ${compose_cmd} up -d --no-build --no-deps workframe-supervisor; }); \
supervisor_id=\$(${compose_cmd} ps -q workframe-supervisor); \
test -n \"\$supervisor_id\"; \
docker exec \"\$supervisor_id\" test -f /opt/install/scripts/apply-update-workframe.sh; \
docker exec \"\$supervisor_id\" test -f /opt/install/scripts/apply-update-hermes.sh"
}

_wf_stack_apply_lock_dir() {
  printf '%s' "${API_DIR}/data/.stack-apply.lock.d"
}

_wf_release_update_lock() {
  rm -rf "$(_wf_stack_apply_lock_dir)" 2>/dev/null || true
}

_wf_acquire_update_lock() {
  local lockdir oldpid
  lockdir="$(_wf_stack_apply_lock_dir)"
  mkdir -p "${API_DIR}/data"
  if mkdir "$lockdir" 2>/dev/null; then
    echo $$ > "$lockdir/pid"
    trap '_wf_release_update_lock' EXIT
    return 0
  fi
  oldpid="$(tr -d '\r\n' < "$lockdir/pid" 2>/dev/null || true)"
  if [[ -n "$oldpid" ]] && kill -0 "$oldpid" 2>/dev/null; then
    echo "ERROR: stack apply already running (pid ${oldpid})" >&2
    exit 1
  fi
  echo "WARN: removing stale stack apply lock (pid ${oldpid:-unknown})" >&2
  rm -rf "$lockdir"
  mkdir "$lockdir" || { echo "ERROR: could not acquire stack apply lock" >&2; exit 1; }
  echo $$ > "$lockdir/pid"
  trap '_wf_release_update_lock' EXIT
}

_wf_recreate_api_and_supervisor() {
  local attempt
  for attempt in 1 2; do
    workframe_prune_created_compose_containers workframe-api
    workframe_prune_created_compose_containers workframe-supervisor
    if [[ "${WORKFRAME_UPDATE_FROM_SUPERVISOR:-}" == "1" ]]; then
      if workframe_compose_recreate up -d --no-build --force-recreate --no-deps workframe-api; then
        # This script runs INSIDE the supervisor container — restarting it here
        # would kill this apply mid-flight. Defer to the very end of the script.
        WF_NEED_SUPERVISOR_RESTART=1
        return 0
      fi
    elif workframe_compose_recreate up -d --build --force-recreate --no-deps workframe-api workframe-supervisor; then
      return 0
    fi
    if [[ "$attempt" -eq 1 ]]; then
      echo "WARN: service recreate failed — pruning stale containers and retrying..." >&2
      sleep 2
    else
      exit 1
    fi
  done
}

_wf_ui_service_name() {
  if workframe_compose config --services 2>/dev/null | grep -qx workframe-ui; then
    printf '%s' workframe-ui
  elif workframe_compose config --services 2>/dev/null | grep -qx workframe; then
    printf '%s' workframe
  fi
}

_wf_ensure_ui_service() {
  local svc
  svc="$(_wf_ui_service_name)"
  [[ -n "$svc" ]] || return 0

  local nginx_conf="$compose_cd/workframe-ui/docker/nginx.conf"
  if [[ -n "${WF_UPDATE_NGINX_SRC:-}" && -f "$WF_UPDATE_NGINX_SRC" ]]; then
    echo "Syncing workframe-ui/docker/nginx.conf -> $nginx_conf"
    mkdir -p "$(dirname "$nginx_conf")"
    local nginx_tmp
    nginx_tmp="$(mktemp "${nginx_conf}.update.XXXXXX")"
    cp "$WF_UPDATE_NGINX_SRC" "$nginx_tmp"
    chmod 0644 "$nginx_tmp" 2>/dev/null || true
    mv -f "$nginx_tmp" "$nginx_conf"
  fi
  if [[ ! -f "$nginx_conf" ]]; then
    echo "ERROR: UI nginx config missing: $nginx_conf" >&2
    exit 1
  fi

  local staged_ui=""
  if [[ -n "${WF_UPDATE_UI_SRC:-}" && -d "$WF_UPDATE_UI_SRC" ]]; then
    staged_ui="${UI_DIR}.update.$$"
    rm -rf "$staged_ui"
    echo "Staging workframe-ui/public -> $staged_ui"
    _wf_sync_tree "$WF_UPDATE_UI_SRC" "$staged_ui"
    _wf_validate_ui_tree "$staged_ui"
    echo "UI update staged and entry assets verified"
    echo "Replacing workframe-ui/public -> $UI_DIR"
    workframe_compose_recreate stop "$svc" 2>/dev/null || true
    workframe_compose_recreate rm -f "$svc" 2>/dev/null || true
    rm -rf "$UI_DIR"
    mv "$staged_ui" "$UI_DIR"
  fi

  workframe_prune_created_compose_containers "$svc"

  # nginx upstreams (gateway/dashboard) must exist, but the UI up must NOT walk
  # the dependency graph: that recreates the supervisor and kills this apply.
  # When the absolute host-bindings overlay is available, recreate these
  # dependencies so an older relative bind (for example /compose/Agents) cannot
  # survive an update. The overlay points at the canonical runtime data and
  # does not remove or replace Agents/, Files/, or API data.
  _wf_ensure_ui_dependency() {
    local dependency="$1"
    workframe_prune_created_compose_containers "$dependency"
    echo "Ensuring dependency $dependency is running..."
    local recreate_args=(up -d --no-build --no-deps)
    if workframe_compose_host_bindings_available; then
      recreate_args+=(--force-recreate)
    else
      recreate_args+=(--no-recreate)
    fi
    if ! workframe_compose_recreate "${recreate_args[@]}" "$dependency"; then
      echo "ERROR: dependency $dependency could not start" >&2
      exit 1
    fi
    workframe_wait_service_running "$dependency" 60
  }

  local dep
  for dep in gateway dashboard; do
    if workframe_compose config --services 2>/dev/null | grep -qx "$dep"; then
      _wf_ensure_ui_dependency "$dep"
    fi
  done

  echo "Ensuring $svc is running..."
  workframe_compose_recreate up -d --no-build --no-deps "$svc"

  local attempt
  for attempt in $(seq 1 30); do
    if workframe_compose_recreate exec -T "$svc" test -f /usr/share/nginx/html/index.html 2>/dev/null \
      && workframe_compose_recreate exec -T "$svc" wget -q -O /dev/null http://127.0.0.1/ 2>/dev/null; then
      echo "UI health check ok ($svc)"
      return 0
    fi
    if [[ "$attempt" -eq 15 ]]; then
      echo "WARN: UI mount stale — removing $svc and retrying..." >&2
      workframe_compose_recreate rm -f "$svc" 2>/dev/null || true
      workframe_compose_recreate up -d --no-build --no-deps "$svc"
    fi
    sleep 1
  done
  echo "ERROR: UI service $svc not healthy after recreate" >&2
  exit 1
}

_wf_sync_env_api_version() {
  local ver="$1"
  local env_file="$compose_cd/.env"
  [[ -n "$ver" && -f "$env_file" ]] || return 0
  if grep -q '^WORKFRAME_API_VERSION=' "$env_file"; then
    sed -i "s/^WORKFRAME_API_VERSION=.*/WORKFRAME_API_VERSION=${ver}/" "$env_file"
  else
    printf '\nWORKFRAME_API_VERSION=%s\n' "$ver" >> "$env_file"
  fi
}

_wf_sync_compose_api_version() {
  local ver="$1"
  local compose_file="$compose_cd/docker-compose.yml"
  [[ -n "$ver" && -f "$compose_file" ]] || return 0
  if grep -qE '^[[:space:]]*- WORKFRAME_API_VERSION=' "$compose_file"; then
    sed -i -E "s/^([[:space:]]*- WORKFRAME_API_VERSION=).*/\1${ver}/" "$compose_file"
  fi
}

_wf_install_paths() {
  local root="$1"
  if [[ -d "$root/services/workframe-api" ]]; then
    API_DIR="$root/services/workframe-api"
    SUP_DIR="$root/services/workframe-supervisor"
    UI_DIR="$root/apps/web/dist"
    if [[ -d "$root/scripts/workframe" ]]; then
      SCRIPTS_DIR="$root/scripts/workframe"
    else
      SCRIPTS_DIR="$root/scripts"
    fi
  else
    API_DIR="$root/workframe-api"
    SUP_DIR="$root/workframe-supervisor"
    UI_DIR="$root/workframe-ui/public"
    if [[ -d "$root/scripts/workframe" ]]; then
      SCRIPTS_DIR="$root/scripts/workframe"
    else
      SCRIPTS_DIR="$root/scripts"
    fi
  fi
}

if [[ "${WF_APPLY_UPDATE_SELF_CHECK:-}" == "1" ]]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo test > "$TMP/t"
  command -v python3 >/dev/null || { echo "self-check: python3 required" >&2; exit 1; }
  python3 -c 'import base64, hashlib, sys; print("sha512-" + base64.b64encode(hashlib.sha512(open(sys.argv[1], "rb").read()).digest()).decode())' "$TMP/t" > "$TMP/t.sha512"
  _wf_prefetched_integrity_ok "$TMP/t"
  echo "apply-update-workframe self-check ok"
  exit 0
fi

workframe_compose_prepare
PROJECT_ROOT="$(_wf_resolve_project_root)"
_wf_install_paths "$PROJECT_ROOT"

echo "=== Workframe update (API + supervisor + UI) ==="
echo "Project root: $PROJECT_ROOT"
echo "Preserves: Agents/, Files/, .env, workframe-api/data, gateway/Hermes profiles"

TARGET_VERSION="${WORKFRAME_UPDATE_VERSION:-}"
NPM_PACKAGE="${WORKFRAME_NPM_PACKAGE:-create-workframe}"
PREFETCH_TARBALL="${WORKFRAME_UPDATE_TARBALL:-}"
TEMPLATE_SYNCED=0
WF_UPDATE_UI_SRC=""
WF_UPDATE_EXTRACT_DIR=""
WF_NEED_SUPERVISOR_RESTART=0

if [[ -n "$PREFETCH_TARBALL" && -f "$PREFETCH_TARBALL" ]]; then
  echo "Applying API-prefetched tarball: $PREFETCH_TARBALL"
  _wf_apply_npm_tarball "$PREFETCH_TARBALL" "${TARGET_VERSION:-latest}" prefetched
  TEMPLATE_SYNCED=1
elif [[ "${WORKFRAME_UPDATE_SKIP_NPM:-1}" == "1" ]] && [[ "${WORKFRAME_UPDATE_ALLOW_NPM:-}" != "1" ]]; then
  echo "Skipping npm template sync (WORKFRAME_UPDATE_SKIP_NPM=1; set WORKFRAME_UPDATE_ALLOW_NPM=1 to fetch)"
  if [[ -n "$PREFETCH_TARBALL" && ! -f "$PREFETCH_TARBALL" ]]; then
    echo "ERROR: prefetch tarball missing: $PREFETCH_TARBALL" >&2
    exit 1
  fi
elif command -v npm >/dev/null 2>&1; then
  if [[ "${WORKFRAME_UPDATE_ALLOW_NPM:-}" == "1" ]] && [[ -z "$TARGET_VERSION" ]]; then
    echo "WORKFRAME_UPDATE_VERSION is required when WORKFRAME_UPDATE_ALLOW_NPM=1" >&2
    exit 1
  fi
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "Fetching ${NPM_PACKAGE}@${TARGET_VERSION:-latest} from npm..."
  if ! (cd "$TMP" && npm pack "${NPM_PACKAGE}@${TARGET_VERSION:-latest}" --silent); then
    echo "npm pack failed (supervisor control-net has no registry access — use API prefetch)" >&2
    exit 1
  fi
  TARBALL="$(ls -1 "$TMP"/${NPM_PACKAGE}-*.tgz 2>/dev/null | head -n1 || true)"
  if [[ -n "$TARBALL" ]]; then
    _wf_apply_npm_tarball "$TARBALL" "${TARGET_VERSION:-latest}" npm
    TEMPLATE_SYNCED=1
  else
    echo "npm pack produced no tarball — skipping template sync" >&2
    exit 1
  fi
else
  echo "Skipping npm template sync (npm missing or WORKFRAME_UPDATE_SKIP_NPM=1)"
fi

# ponytail: tarball sync rewrites this script on disk — must re-exec or old logic keeps running
if [[ "$TEMPLATE_SYNCED" == "1" && -z "${WF_APPLY_REEXEC:-}" ]]; then
  echo "Re-execing apply-update-workframe.sh after template sync..."
  export WF_APPLY_REEXEC=1
  exec bash "${SCRIPTS_DIR}/apply-update-workframe.sh"
fi

_wf_acquire_update_lock

if [[ -n "$TARGET_VERSION" && "$TEMPLATE_SYNCED" != "1" ]]; then
  echo "ERROR: template sync did not run — refusing rebuild-only update for create-workframe@${TARGET_VERSION}." >&2
  echo "Prefetch the npm pack to workframe-api/data/.update-staging or set WORKFRAME_UPDATE_ALLOW_NPM=1." >&2
  exit 1
fi

if [[ "$TEMPLATE_SYNCED" == "1" && -n "$TARGET_VERSION" ]]; then
  echo "Syncing compose env to v${TARGET_VERSION} before container recreate..."
  _wf_commit_compose_alignment "$TARGET_VERSION"
fi

echo "Rebuilding workframe-api and workframe-supervisor..."
workframe_compose build workframe-api workframe-supervisor
_wf_recreate_api_and_supervisor

_wf_ensure_ui_service

if [[ "$TEMPLATE_SYNCED" == "1" && -n "$TARGET_VERSION" ]]; then
  _wf_verify_version_alignment "$TARGET_VERSION"
  _wf_record_package_version "$TARGET_VERSION"
fi

workframe_docker_cleanup_after_update

rm -rf "${WF_UPDATE_EXTRACT_DIR:-}" 2>/dev/null || true

# Last step on purpose: the sibling recreates the supervisor (our own parent
# container). Everything above must already be done and pinned by now.
if [[ "${WF_NEED_SUPERVISOR_RESTART:-0}" == "1" ]]; then
  _wf_schedule_supervisor_restart
fi

echo "=== Workframe update complete ==="
