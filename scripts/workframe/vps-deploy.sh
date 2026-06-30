#!/usr/bin/env bash
# Deploy Workframe stack on VPS (clean compose dir, preserve runtime/).
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/workframe/repo/infra/compose/workframe}"
PROJECT_ROOT="${PROJECT_ROOT:-/opt/workframe/repo}"

_vps_setup_public_https_if_configured() {
  if [[ ! -f "$COMPOSE_DIR/.env" ]]; then
    return 0
  fi
  set -a
  # shellcheck disable=SC1091
  source "$COMPOSE_DIR/.env"
  set +a
  local host="${WORKFRAME_PUBLIC_HOST:-}"
  if [[ -z "$host" && -n "${APP_BASE_URL:-}" ]]; then
    host="${APP_BASE_URL#https://}"
    host="${host#http://}"
    host="${host%%/*}"
  fi
  if [[ -z "$host" || "$host" == *127.0.0.1* || "$host" == localhost* ]]; then
    return 0
  fi
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Skip auto HTTPS: not root."
    return 0
  fi
  echo "Auto HTTPS for $host (DNS can be added before or after; cert waits for DNS)..."
  bash "$PROJECT_ROOT/scripts/workframe/setup-public-https.sh" "$host" "${WORKFRAME_UI_PORT:-18644}" \
    || echo "HTTPS setup returned non-zero (often DNS not ready yet — Caddy retries)."
}

cd "$COMPOSE_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from example — edit secrets before production use."
fi

mkdir -p "$PROJECT_ROOT/runtime/Agents" "$PROJECT_ROOT/runtime/Files" "$PROJECT_ROOT/runtime/workframe-api-data"
chmod -R a+rwX "$PROJECT_ROOT/runtime/Agents" "$PROJECT_ROOT/runtime/Files" 2>/dev/null || true
bash "$PROJECT_ROOT/scripts/workframe/bootstrap-native.sh"

cd "$PROJECT_ROOT"
# ponytail: full pnpm workspace install fails on VPS (optional packages); UI only needs apps/web.
cd "$PROJECT_ROOT/apps/web"
npm install
npm run build

cd "$COMPOSE_DIR"
COMPOSE_FILES=(-f docker-compose.yml)
if grep -qE '^WORKFRAME_DEPLOYMENT_MODE=public_multi_user' .env 2>/dev/null; then
  COMPOSE_FILES+=(-f docker-compose.public.yml)
fi
docker compose "${COMPOSE_FILES[@]}" down --remove-orphans || true
docker compose "${COMPOSE_FILES[@]}" up -d --build

_vps_setup_public_https_if_configured

echo "Stack up."
echo "UI: http://127.0.0.1:\${WORKFRAME_UI_PORT:-18644}/"
