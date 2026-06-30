#!/usr/bin/env bash
# Append production stack secrets to a Workframe .env (idempotent).
# Usage: bash scripts/workframe/setup-stack-secrets.sh path/to/.env
set -euo pipefail

ENV_FILE="${1:-/workspace/.env}"

append_if_missing() {
  local key="$1"
  local value="$2"
  local comment="${3:-}"
  if [[ -f "$ENV_FILE" ]] && grep -q "^${key}=" "$ENV_FILE"; then
    echo "${key} already exists in ${ENV_FILE}"
    return 0
  fi
  mkdir -p "$(dirname "$ENV_FILE")"
  {
    [[ -n "$comment" ]] && printf '\n# %s\n' "$comment"
    printf '%s=%s\n' "$key" "$value"
  } >>"$ENV_FILE"
  echo "${key} generated and appended to ${ENV_FILE}"
}

rand_hex() {
  openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}

rand_b64() {
  python3 - <<'PY'
import base64, os
print(base64.b64encode(os.urandom(32)).decode())
PY
}

rand_proxy() {
  python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

append_if_missing WORKFRAME_SUPERVISOR_TOKEN "${WORKFRAME_SUPERVISOR_TOKEN:-$(rand_hex)}" \
  "Workframe supervisor token. Keep this secret."
append_if_missing WORKFRAME_PROXY_TOKEN "${WORKFRAME_PROXY_TOKEN:-$(rand_proxy)}" \
  "Internal LLM/action proxy secret — gateway + API must match."
append_if_missing WORKFRAME_VAULT_KEK "${WORKFRAME_VAULT_KEK:-$(rand_b64)}" \
  "Credential vault KEK (32-byte base64). Required for public_multi_user."
