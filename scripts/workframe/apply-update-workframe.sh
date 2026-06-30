#!/usr/bin/env bash
# Safe Workframe update — sync npm template (optional), rebuild API/supervisor/UI containers. Never wipes runtime/DB.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=compose-docker-host.sh
source "$SCRIPT_DIR/compose-docker-host.sh"

workframe_compose_prepare
PROJECT_ROOT="${WORKFRAME_HOST_PROJECT_ROOT:-${WORKFRAME_PROJECT_ROOT:-$compose_cd}}"

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
    EXPECTED="$(npm view "${NPM_PACKAGE}@${TARGET_VERSION:-latest}" dist.integrity --silent 2>/dev/null || true)"
    if [[ -n "$EXPECTED" ]]; then
      ACTUAL="sha512-$(sha512sum "$TARBALL" | awk '{print $1}' | xxd -r -p | base64 | tr -d '\n')"
      if [[ "$ACTUAL" != "$EXPECTED" ]]; then
        echo "integrity mismatch for ${NPM_PACKAGE}@${TARGET_VERSION:-latest}" >&2
        exit 1
      fi
      echo "integrity ok: ${NPM_PACKAGE}@${TARGET_VERSION:-latest}"
    fi
    tar -xf "$TARBALL" -C "$TMP"
    PKG="$TMP/package"
    for dir in workframe-api workframe-supervisor; do
      if [[ -d "$PKG/$dir" ]]; then
        echo "Syncing $dir/"
        mkdir -p "$PROJECT_ROOT/$dir"
        cp -a "$PKG/$dir/." "$PROJECT_ROOT/$dir/"
      fi
    done
    if [[ -d "$PKG/workframe-ui/public" ]]; then
      echo "Syncing workframe-ui/public/"
      mkdir -p "$PROJECT_ROOT/workframe-ui/public"
      cp -a "$PKG/workframe-ui/public/." "$PROJECT_ROOT/workframe-ui/public/"
    fi
    for script in apply-update-hermes.sh apply-update-workframe.sh restart-gateway-hermes.sh compose-docker-host.sh update-hermes.sh; do
      if [[ -f "$PKG/scripts/$script" ]]; then
        cp -a "$PKG/scripts/$script" "$PROJECT_ROOT/scripts/workframe/$script"
        chmod +x "$PROJECT_ROOT/scripts/workframe/$script" 2>/dev/null || true
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
