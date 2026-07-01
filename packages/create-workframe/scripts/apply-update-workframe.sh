#!/usr/bin/env bash
# Safe Workframe update — sync npm template (optional), rebuild API/supervisor/UI containers. Never wipes runtime/DB.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=compose-docker-host.sh
source "$SCRIPT_DIR/compose-docker-host.sh"

# ponytail: npm integrity via python3 — Alpine supervisor has no xxd
_wf_npm_integrity_ok() {
  local tarball="$1" pkg="$2" ver="${3:-latest}"
  local expected actual
  expected="$(npm view "${pkg}@${ver}" dist.integrity --silent 2>/dev/null || true)"
  [[ -n "$expected" ]] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    echo "warn: python3 missing — skipping npm integrity check" >&2
    return 0
  fi
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
  if ! _wf_npm_integrity_ok "$TMP/t" create-workframe latest 2>/dev/null; then
    : # empty file won't match registry integrity — exercise python path only
  fi
  command -v python3 >/dev/null || { echo "self-check: python3 required" >&2; exit 1; }
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

if [[ "${WORKFRAME_UPDATE_SKIP_NPM:-1}" == "1" ]] && [[ "${WORKFRAME_UPDATE_ALLOW_NPM:-}" != "1" ]]; then
  echo "Skipping npm template sync (WORKFRAME_UPDATE_SKIP_NPM=1; set WORKFRAME_UPDATE_ALLOW_NPM=1 to fetch)"
elif command -v npm >/dev/null 2>&1; then
  if [[ "${WORKFRAME_UPDATE_ALLOW_NPM:-}" == "1" ]] && [[ -z "$TARGET_VERSION" ]]; then
    echo "WORKFRAME_UPDATE_VERSION is required when WORKFRAME_UPDATE_ALLOW_NPM=1" >&2
    exit 1
  fi
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "Fetching ${NPM_PACKAGE}@${TARGET_VERSION:-latest} from npm..."
  (cd "$TMP" && npm pack "${NPM_PACKAGE}@${TARGET_VERSION:-latest}" --silent)
  TARBALL="$(ls -1 "$TMP"/${NPM_PACKAGE}-*.tgz 2>/dev/null | head -n1 || true)"
  if [[ -n "$TARBALL" ]]; then
    if ! _wf_npm_integrity_ok "$TARBALL" "$NPM_PACKAGE" "${TARGET_VERSION:-latest}"; then
      echo "integrity mismatch for ${NPM_PACKAGE}@${TARGET_VERSION:-latest}" >&2
      exit 1
    fi
    echo "integrity ok: ${NPM_PACKAGE}@${TARGET_VERSION:-latest}"
    tar -xf "$TARBALL" -C "$TMP"
    PKG="$TMP/package"
    if [[ -d "$PKG/workframe-api" ]]; then
      echo "Syncing workframe-api -> $API_DIR"
      _wf_sync_tree "$PKG/workframe-api" "$API_DIR"
    fi
    if [[ -d "$PKG/workframe-supervisor" ]]; then
      echo "Syncing workframe-supervisor -> $SUP_DIR"
      _wf_sync_tree "$PKG/workframe-supervisor" "$SUP_DIR"
    fi
    if [[ -d "$PKG/workframe-ui/public" ]]; then
      echo "Syncing workframe-ui/public -> $UI_DIR"
      _wf_sync_tree "$PKG/workframe-ui/public" "$UI_DIR"
    fi
    for script in apply-update-hermes.sh apply-update-workframe.sh restart-gateway-hermes.sh compose-docker-host.sh update-hermes.sh; do
      if [[ -f "$PKG/scripts/$script" ]]; then
        cp -a "$PKG/scripts/$script" "$SCRIPTS_DIR/$script"
        chmod +x "$SCRIPTS_DIR/$script" 2>/dev/null || true
      fi
    done
  else
    echo "npm pack produced no tarball — skipping template sync"
  fi
else
  echo "Skipping npm template sync (npm missing or WORKFRAME_UPDATE_SKIP_NPM=1)"
fi

echo "Rebuilding workframe-api and workframe-supervisor..."
workframe_compose build workframe-api workframe-supervisor
workframe_compose up -d --build --no-deps workframe-api workframe-supervisor

if workframe_compose config --services 2>/dev/null | grep -qx workframe-ui; then
  workframe_compose up -d --no-deps workframe-ui || workframe_compose restart workframe-ui || true
elif workframe_compose config --services 2>/dev/null | grep -qx workframe; then
  workframe_compose up -d --no-deps workframe || workframe_compose restart workframe || true
fi

echo "=== Workframe update complete ==="
