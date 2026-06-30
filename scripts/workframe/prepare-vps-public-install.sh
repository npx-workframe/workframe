#!/usr/bin/env bash
# TUNNEL E2E ONLY — normalizes VPS compose .env for Playwright against http://127.0.0.1 tunnel.
# DO NOT use on a live https:// public install (WORKFRAME_E2E=1 exposes OTP in JSON during install — 0020 F1).
set -euo pipefail
if [[ "${WORKFRAME_TUNNEL_E2E:-}" != "1" ]]; then
  echo "Refusing: set WORKFRAME_TUNNEL_E2E=1 to acknowledge tunnel-only E2E prep (not production)." >&2
  exit 1
fi
COMPOSE_DIR="${1:-/opt/workframe/repo/infra/compose/workframe}"
ENV_FILE="$COMPOSE_DIR/.env"
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE"; exit 1; }

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

set_kv WORKFRAME_PROJECT Workframe
set_kv WORKFRAME_DEPLOYMENT_MODE public_multi_user
set_kv WORKFRAME_E2E 1
set_kv APP_BASE_URL "${APP_BASE_URL:?set APP_BASE_URL for tunnel E2E}"

grep -E '^WORKFRAME_(PROJECT|DEPLOYMENT_MODE|E2E|UI_PORT|API_PORT)|^APP_BASE_URL=' "$ENV_FILE"
