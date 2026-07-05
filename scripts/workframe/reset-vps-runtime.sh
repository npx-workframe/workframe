#!/usr/bin/env bash
# VPS dogfood reset = npx create-workframe on Docker. Period.
#
# Wipes prior install at INSTALL_ROOT/PROJECT, stops legacy repo compose if present,
# then runs ONLY create-workframe (package owns bootstrap + docker + Phase B).
#
# Usage:
#   bash reset-vps-runtime.sh
#   bash reset-vps-runtime.sh /path/to/create-workframe-0.1.7.tgz
#
# Env: WORKFRAME_INSTALL_ROOT (default /opt/workframe)
#      WORKFRAME_PROJECT_NAME (default MyBusiness)
#      WORKFRAME_SLOT (default 2)
#      CREATE_WORKFRAME_VERSION (default 0.1.7) when no pack tarball
set -euo pipefail

INSTALL_ROOT="${WORKFRAME_INSTALL_ROOT:-/opt/workframe}"
PROJECT="${WORKFRAME_PROJECT_NAME:-MyBusiness}"
SLOT="${WORKFRAME_SLOT:-2}"
PACK_TGZ="${1:-}"
INSTALL_DIR="$INSTALL_ROOT/$PROJECT"
REPO_ROOT="${WORKFRAME_REPO_ROOT:-/opt/workframe/repo}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

compose_down() {
  local dir="$1"
  [[ -f "$dir/docker-compose.yml" ]] || return 0
  ok "compose down $dir"
  (cd "$dir" && docker compose down -v --remove-orphans 2>/dev/null) || true
  for overlay in docker-compose.public.yml docker-compose.dev-authority.yml; do
    [[ -f "$dir/$overlay" ]] || continue
    (cd "$dir" && docker compose -f docker-compose.yml -f "$overlay" down -v --remove-orphans 2>/dev/null) || true
  done
}

echo "=== VPS dogfood reset (create-workframe only) ==="

compose_down "$INSTALL_DIR"
compose_down "$REPO_ROOT/infra/compose/workframe"

if [[ -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
  ok "removed $INSTALL_DIR"
fi

mkdir -p "$INSTALL_ROOT"

if [[ -n "$PACK_TGZ" ]]; then
  [[ -f "$PACK_TGZ" ]] || fail "missing pack: $PACK_TGZ"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  tar -xzf "$PACK_TGZ" -C "$TMP"
  PKG="$TMP/package"
  [[ -f "$PKG/bin/create-workframe.js" ]] || fail "pack missing bin/create-workframe.js"
  ok "create-workframe from pack"
  (
    cd "$PKG"
    node bin/create-workframe.js "$PROJECT" \
      --out "$INSTALL_ROOT" \
      --slot "$SLOT" \
      --deploy docker \
      --force \
      --run-docker-pull \
      --allow-install-actions
  )
else
  command -v npx >/dev/null 2>&1 || fail "npx required (or pass pack .tgz)"
  ok "npx create-workframe@${CREATE_WORKFRAME_VERSION:-0.1.7}"
  (
    cd "$INSTALL_ROOT"
    npx --yes "create-workframe@${CREATE_WORKFRAME_VERSION:-0.1.7}" "$PROJECT" \
      --out "$INSTALL_ROOT" \
      --slot "$SLOT" \
      --deploy docker
  )
fi

[[ -f "$INSTALL_DIR/docker-compose.yml" ]] || fail "install missing after create-workframe: $INSTALL_DIR"

UI_PORT="$(grep -E '^WORKFRAME_UI_PORT=' "$INSTALL_DIR/.env" 2>/dev/null | tail -n1 | cut -d= -f2- || echo 28644)"
API_PORT="$(grep -E '^WORKFRAME_API_PORT=' "$INSTALL_DIR/.env" 2>/dev/null | tail -n1 | cut -d= -f2- || echo 29120)"

echo ""
echo "VPS dogfood reset complete — finish wizard in browser or it did not boot."
echo "  Install dir  $INSTALL_DIR"
echo "  UI           http://127.0.0.1:${UI_PORT}/"
echo "  API health   http://127.0.0.1:${API_PORT}/api/health"
