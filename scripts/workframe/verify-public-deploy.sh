#!/usr/bin/env bash
# Fail-closed preflight for WORKFRAME_DEPLOYMENT_MODE=public_multi_user.
# Usage: bash scripts/workframe/verify-public-deploy.sh [compose-dir]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_DIR="${1:-$ROOT/infra/compose/workframe}"
ENV_FILE="$COMPOSE_DIR/.env"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"

fail() { echo "FAIL: $*" >&2; exit 1; }
warn() { echo "WARN: $*" >&2; }
ok() { echo "OK: $*"; }
info() { echo "INFO: $*"; }

gateway_container_name() {
  local name
  name="$(grep -A20 '^  gateway:' "$COMPOSE_FILE" | grep 'container_name:' | head -n1 | sed 's/.*container_name:[[:space:]]*//' | tr -d '\r"')"
  printf '%s' "${name:-workframe-gateway}"
}

report_egress_posture() {
  local gw force_broker gw_on_control internal_control egress_overlay
  gw="$(gateway_container_name)"
  force_broker="$(env_val WORKFRAME_FORCE_AGENT_EGRESS_BROKER)"
  egress_overlay="$COMPOSE_DIR/docker-compose.egress-broker.yml"

  if grep -A30 '^  gateway:' "$COMPOSE_FILE" | grep -q 'control-net'; then
    gw_on_control=yes
  else
    gw_on_control=no
  fi
  if grep -A5 'control-net:' "$COMPOSE_FILE" | grep -q 'internal:[[:space:]]*true'; then
    internal_control=yes
  else
    internal_control=no
  fi

  info "egress gateway_container=$gw"
  info "egress gateway_on_control_net=$gw_on_control (expected no)"
  info "egress control_net_internal=$internal_control (expected yes)"
  [[ "$gw_on_control" == "no" ]] || fail "gateway must not join control-net"
  [[ "$internal_control" == "yes" ]] || warn "control-net is not marked internal:true"

  if command -v docker >/dev/null 2>&1 && docker inspect "$gw" >/dev/null 2>&1; then
    local nets
    nets="$(docker inspect "$gw" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null || true)"
    info "egress gateway_networks=${nets:-<unknown>}"
    if echo "$nets" | grep -qi 'control'; then
      fail "running gateway is attached to a control network"
    fi
    if [[ "$force_broker" =~ ^(1|true|yes|on)$ ]]; then
      if docker inspect workframe-gateway-egress-guard >/dev/null 2>&1; then
        info "egress gateway_egress_posture=provider_hosts_blocked (egress-guard sidecar)"
      else
        fail "WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true but gateway-egress-guard is not running"
      fi
    else
      info "egress gateway_egress_posture=unrestricted_general (broker for LLM/action providers)"
    fi
  else
    info "egress gateway_egress_posture=unknown (gateway container not running)"
  fi

  info "egress broker_path=config_plus_leases (/internal/llm/*, /internal/action/*)"
  info "egress general_internet=allowed (research, terminal, public APIs)"
  info "egress broker_latency=per-request lease validation (no human approval gate)"

  if [[ "$force_broker" =~ ^(1|true|yes|on)$ ]]; then
    [[ -f "$egress_overlay" ]] || fail "missing $egress_overlay (required when WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true)"
    grep -q 'gateway-egress-guard' "$egress_overlay" || fail "egress overlay missing gateway-egress-guard service"
    ok "forced broker egress overlay present"
  fi
  ok "egress posture reported"
}

report_supervisor_constraints() {
  local public_overlay="$COMPOSE_DIR/docker-compose.public.yml"
  if [[ -f "$public_overlay" ]]; then
    grep -q 'WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC=0' "$public_overlay" \
      || fail "docker-compose.public.yml must set WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC=0"
    if grep -A30 '^  workframe-api:' "$public_overlay" | grep -q '/var/run/docker.sock'; then
      fail "docker-compose.public.yml must not mount docker.sock on workframe-api"
    fi
    ok "supervisor public overlay constraints"
  else
    warn "docker-compose.public.yml missing — skipping supervisor overlay checks"
  fi
}

report_broker_audit_schema() {
  local data_dir
  data_dir="$(cd "$ROOT" && pwd)/runtime/workframe-api-data"
  if [[ ! -d "$data_dir" ]]; then
    info "broker_audit schema=skipped (no runtime/workframe-api-data)"
    return
  fi
  python3 - "$data_dir" <<'PY' || fail "broker_audit_events table missing (run API once or apply migration)"
import sqlite3, sys
from pathlib import Path
db = Path(sys.argv[1]) / "workframe.db"
if not db.is_file():
    print("skip: no workframe.db yet")
    raise SystemExit(0)
conn = sqlite3.connect(str(db))
row = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='broker_audit_events'"
).fetchone()
conn.close()
if not row:
    raise SystemExit(1)
PY
  ok "broker audit schema"
}

report_backup_restore_evidence() {
  local backup_doc="$ROOT/infra/compose/workframe/PUBLIC_DEPLOY.md"
  [[ -f "$backup_doc" ]] || fail "missing PUBLIC_DEPLOY.md backup section"
  grep -qi 'backup' "$backup_doc" || fail "PUBLIC_DEPLOY.md missing backup guidance"
  grep -qi 'rollback\|restore' "$backup_doc" || fail "PUBLIC_DEPLOY.md missing restore/rollback guidance"
  ok "backup/restore documented"
}

[[ -f "$ENV_FILE" ]] || fail "missing $ENV_FILE"
[[ -f "$COMPOSE_FILE" ]] || fail "missing $COMPOSE_FILE"

env_val() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '\r' || true
}

MODE="$(env_val WORKFRAME_DEPLOYMENT_MODE)"
MODE="${MODE:-trusted_team}"
if [[ "$MODE" != "public_multi_user" ]]; then
  ok "WORKFRAME_DEPLOYMENT_MODE=$MODE (skipping public checks; pass nothing to force public)"
  exit 0
fi

ok "checking public_multi_user preflight"

if [[ "$(env_val DEV_LOCAL_UNSAFE)" =~ ^(1|true|yes|on)$ ]]; then
  fail "DEV_LOCAL_UNSAFE must be off for public_multi_user"
fi
if [[ "$(env_val SECURE_MODE)" != "true" ]]; then
  fail "SECURE_MODE=true required"
fi

for key in WORKFRAME_SUPERVISOR_TOKEN WORKFRAME_API_TOKEN WORKFRAME_PROXY_TOKEN WORKFRAME_VAULT_KEK \
  ZK_AUTH_HMAC_KEY ZK_AUTH_ENCRYPTION_KEY ZK_AUTH_SESSION_SECRET \
  SMTP_HOST SMTP_USER SMTP_PASS EMAIL_FROM; do
  [[ -n "$(env_val "$key")" ]] || fail "$key is empty"
done

APP_URL="$(env_val APP_BASE_URL)"
[[ "$APP_URL" == https://* ]] || fail "APP_BASE_URL must be https:// (got ${APP_URL:-<empty>})"

enc_key="$(env_val ZK_AUTH_ENCRYPTION_KEY)"
if [[ -n "$enc_key" ]]; then
  python3 - "$enc_key" <<'PY' || fail "ZK_AUTH_ENCRYPTION_KEY must be base64-encoded 32 bytes (not hex)"
import base64, sys
raw = base64.b64decode(sys.argv[1].strip())
assert len(raw) == 32
PY
  ok "ZK_AUTH_ENCRYPTION_KEY format"
fi

if [[ "$(env_val WORKFRAME_E2E)" =~ ^(1|true|yes|on)$ ]] && [[ "$APP_URL" == https://* ]]; then
  fail "WORKFRAME_E2E must be off for public HTTPS deploy"
fi

if grep -A40 '^  gateway:' "$COMPOSE_FILE" | grep -q 'env_file:'; then
  fail "gateway must not use env_file in docker-compose.yml"
fi
if ! grep -q 'control-net' "$COMPOSE_FILE"; then
  fail "control-net missing from docker-compose.yml"
fi

UI_PORT="$(env_val WORKFRAME_UI_PORT)"
UI_PORT="${UI_PORT:-18644}"
API_PORT="$(env_val WORKFRAME_API_PORT)"
API_PORT="${API_PORT:-19120}"

if command -v curl >/dev/null 2>&1; then
  health="$(curl -fsS "http://127.0.0.1:${API_PORT}/api/health" 2>/dev/null || true)"
  if [[ -z "$health" ]]; then
    warn "API health unreachable on 127.0.0.1:${API_PORT} (stack down?)"
  else
    echo "$health" | grep -q 'public_multi_user' || fail "API health missing deployment_mode public_multi_user"
    echo "$health" | grep -q '"mode": "secure"' || fail "API not in secure mode"
    echo "$health" | grep -q '"proxy_token_configured": true' || fail "API proxy_token_configured is false"
    echo "$health" | grep -q '"vault_envelope": true' || fail "API vault_envelope is false"
    echo "$health" | grep -q '"docker_sock_on_api": false' || fail "API still has docker.sock mounted"
    echo "$health" | grep -q 'install_window_open' || warn "API health missing install_window_open"
    echo "$health" | grep -q 'workframe_e2e' || warn "API health missing workframe_e2e"
    echo "$health" | grep -q 'dev_local_unsafe' || warn "API health missing dev_local_unsafe"
    ok "API health"
    snapshot_code="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/api/snapshot" || true)"
    [[ "$snapshot_code" == "401" ]] || fail "anonymous /api/snapshot returned ${snapshot_code:-<empty>} (expected 401)"
    ok "anonymous /api/snapshot denied"
  fi
  dash_code="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${UI_PORT}/hermes-dashboard/" || true)"
  [[ "$dash_code" == "403" ]] || warn "hermes-dashboard without session returned $dash_code (expected 403)"
else
  warn "curl not found — skipping HTTP checks"
fi

if command -v docker >/dev/null 2>&1 && docker inspect "$(gateway_container_name)" >/dev/null 2>&1; then
  gw_env="$(docker inspect "$(gateway_container_name)" --format '{{range .Config.Env}}{{println .}}{{end}}')"
  for marker in WORKFRAME_SUPERVISOR_TOKEN ZK_AUTH_ SMTP_PASS; do
    echo "$gw_env" | grep -q "$marker" && fail "gateway env contains $marker"
  done
  ok "gateway env allowlist"
else
  warn "$(gateway_container_name) not running — skipping docker inspect"
fi

report_egress_posture

report_supervisor_constraints
report_broker_audit_schema
report_backup_restore_evidence

ok "public_multi_user preflight passed"
