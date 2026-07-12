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
    echo "Syncing workframe-ui/public -> $UI_DIR"
    _wf_sync_tree "$pkg/workframe-ui/public" "$UI_DIR"
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
  _wf_sync_from_pack_dir "$extract_dir/package"
  rm -rf "$extract_dir"
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

if [[ -n "$PREFETCH_TARBALL" && -f "$PREFETCH_TARBALL" ]]; then
  echo "Applying API-prefetched tarball: $PREFETCH_TARBALL"
  _wf_apply_npm_tarball "$PREFETCH_TARBALL" "${TARGET_VERSION:-latest}" prefetched
elif [[ "${WORKFRAME_UPDATE_SKIP_NPM:-1}" == "1" ]] && [[ "${WORKFRAME_UPDATE_ALLOW_NPM:-}" != "1" ]]; then
  echo "Skipping npm template sync (WORKFRAME_UPDATE_SKIP_NPM=1; set WORKFRAME_UPDATE_ALLOW_NPM=1 to fetch)"
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
  else
    echo "npm pack produced no tarball — skipping template sync" >&2
    exit 1
  fi
else
  echo "Skipping npm template sync (npm missing or WORKFRAME_UPDATE_SKIP_NPM=1)"
fi

echo "Rebuilding workframe-api and workframe-supervisor..."
workframe_compose build workframe-api workframe-supervisor
if [[ "${WORKFRAME_UPDATE_FROM_SUPERVISOR:-}" == "1" ]]; then
  # ponytail: supervisor cannot recreate itself inside the stack.apply request — defer after handler returns
  workframe_compose_host_bindings up -d --no-build --no-deps workframe-api
  (
    sleep 3
    workframe_compose_host_bindings up -d --no-build --no-deps workframe-supervisor
  ) >/tmp/workframe-supervisor-restart.log 2>&1 &
else
  workframe_compose up -d --build --no-deps workframe-api workframe-supervisor
fi

if workframe_compose config --services 2>/dev/null | grep -qx workframe-ui; then
  workframe_compose_host_bindings up -d --no-build --no-deps workframe-ui || workframe_compose_host_bindings restart workframe-ui || true
elif workframe_compose config --services 2>/dev/null | grep -qx workframe; then
  workframe_compose_host_bindings up -d --no-build --no-deps workframe || workframe_compose_host_bindings restart workframe || true
fi

_wf_record_package_version "${TARGET_VERSION:-}"

echo "=== Workframe update complete ==="
