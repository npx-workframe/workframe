#!/usr/bin/env bash
# Apply canonical hotfix tarball to a pack-style install (ABX on VPS or AB locally).
set -euo pipefail
TARBALL="${1:-/tmp/wf-014-deploy.tgz}"
INSTALL_DIR="${2:-/opt/workframe/ABX}"
STAGE="/tmp/wf-014-deploy-$$"

[[ -f "$TARBALL" ]] || { echo "missing tarball: $TARBALL"; exit 1; }
[[ -d "$INSTALL_DIR" ]] || { echo "missing install: $INSTALL_DIR"; exit 1; }

mkdir -p "$STAGE"
tar -xzf "$TARBALL" -C "$STAGE"

rsync -a --exclude data "$STAGE/workframe-api/" "$INSTALL_DIR/workframe-api/"
rsync -a "$STAGE/workframe-supervisor/" "$INSTALL_DIR/workframe-supervisor/"
mkdir -p "$INSTALL_DIR/workframe-ui/public"
rsync -a "$STAGE/workframe-ui/public/" "$INSTALL_DIR/workframe-ui/public/"
cp -a "$STAGE/scripts/"*.sh "$INSTALL_DIR/scripts/"
chmod +x "$INSTALL_DIR/scripts/"*.sh

cd "$INSTALL_DIR"
COMPOSE_ARGS=(-f docker-compose.yml -f docker-compose.public.yml)
if [[ -f docker-compose.host-bindings.yml ]]; then
  COMPOSE_ARGS+=(-f docker-compose.host-bindings.yml)
fi

docker compose "${COMPOSE_ARGS[@]}" build workframe-api workframe-supervisor
docker compose "${COMPOSE_ARGS[@]}" up -d --no-deps workframe-api workframe-supervisor workframe
docker compose "${COMPOSE_ARGS[@]}" restart workframe || true

API_PORT=$(grep -E '^WORKFRAME_API_PORT=' .env | cut -d= -f2)
UI_PORT=$(grep -E '^WORKFRAME_UI_PORT=' .env | cut -d= -f2)
echo "--- health ---"
curl -s "http://127.0.0.1:${API_PORT}/api/health"
echo
curl -s -o /dev/null -w "ui:%{http_code}\n" "http://127.0.0.1:${UI_PORT}/"
