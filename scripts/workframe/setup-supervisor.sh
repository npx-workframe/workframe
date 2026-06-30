#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/workspace/.env}"
TOKEN="${WORKFRAME_SUPERVISOR_TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
  TOKEN="$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
fi

if [[ -f "$ENV_FILE" ]] && grep -q '^WORKFRAME_SUPERVISOR_TOKEN=' "$ENV_FILE"; then
  echo "WORKFRAME_SUPERVISOR_TOKEN already exists in $ENV_FILE"
  exit 0
fi

mkdir -p "$(dirname "$ENV_FILE")"
{
  printf '\n# Workframe supervisor token. Keep this secret.\n'
  printf 'WORKFRAME_SUPERVISOR_TOKEN=%s\n' "$TOKEN"
} >> "$ENV_FILE"

echo "WORKFRAME_SUPERVISOR_TOKEN generated and appended to $ENV_FILE"
