#!/usr/bin/env bash
# Wipe + reinstall VPS sandbox from create-workframe npm pack (not git/scp deploy).
# Usage: bash vps-pack-install-remote.sh /tmp/create-workframe.tgz [MyBusiness] [/opt/workframe] [2] [https://your.public.host]
set -euo pipefail

TGZ="${1:?pack tarball required}"
PROJECT_NAME="${2:-MyBusiness}"
OUT_ROOT="${3:-/opt/workframe}"
SLOT="${4:-2}"
PUBLIC_URL="${5:-}"
if [[ -z "$PUBLIC_URL" ]]; then
  echo "PUBLIC_URL required as 5th argument (e.g. https://your.public.host)" >&2
  exit 1
fi
INSTALL_DIR="$OUT_ROOT/$PROJECT_NAME"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

[[ -f "$TGZ" ]] || fail "missing pack: $TGZ"
command -v node >/dev/null 2>&1 || fail "node required on VPS"
command -v docker >/dev/null 2>&1 || fail "docker required on VPS"

# Stop any stack using slot ports or old install dir.
REPO_ROOT="${WORKFRAME_REPO_ROOT:-$OUT_ROOT/repo}"
for dir in "$INSTALL_DIR" "$REPO_ROOT"; do
  if [[ -f "$dir/docker-compose.yml" ]]; then
    (cd "$dir" && docker compose down --remove-orphans 2>/dev/null) || true
  fi
  if [[ -f "$dir/infra/compose/workframe/docker-compose.yml" ]]; then
    (cd "$dir/infra/compose/workframe" && docker compose down --remove-orphans 2>/dev/null) || true
  fi
done

if [[ -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
  ok "removed $INSTALL_DIR"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$TGZ" -C "$TMP"
PKG="$TMP/package"
[[ -f "$PKG/bin/create-workframe.js" ]] || fail "pack missing bin/create-workframe.js"

mkdir -p "$OUT_ROOT"
(
  cd "$PKG"
  node bin/create-workframe.js "$PROJECT_NAME" \
    --out "$OUT_ROOT" \
    --slot "$SLOT" \
    --deploy docker \
    --ci \
    --no-launch \
    --run-docker-pull \
    --allow-install-actions
)

[[ -d "$INSTALL_DIR" ]] || fail "scaffold missing: $INSTALL_DIR"

mkdir -p "$INSTALL_DIR/Agents/profiles" "$INSTALL_DIR/Files" "$INSTALL_DIR/workframe-api/data"
chmod -R a+rwX "$INSTALL_DIR/Agents" "$INSTALL_DIR/Files" "$INSTALL_DIR/workframe-api" 2>/dev/null || true

# Public overlay only — no secret carry from prior installs (sign-off must exercise wizard).
python3 - "$INSTALL_DIR/.env" "$PUBLIC_URL" <<'PY'
import re, sys
from pathlib import Path

env_path, public_url = sys.argv[1:3]
env = Path(env_path)
text = env.read_text(encoding="utf-8")

def set_kv(key, val):
    global text
    line = f"{key}={val}"
    if re.search(rf"^{re.escape(key)}=", text, re.M):
        text = re.sub(rf"^{re.escape(key)}=.*$", line, text, flags=re.M)
    else:
        text += ("\n" if not text.endswith("\n") else "") + line + "\n"

set_kv("WORKFRAME_DEPLOYMENT_MODE", "public_multi_user")
set_kv("SECURE_MODE", "true")
set_kv("DEV_LOCAL_UNSAFE", "false")
set_kv("APP_BASE_URL", public_url.rstrip("/"))
host = public_url.split("://", 1)[-1].split("/")[0]
set_kv("ALLOWED_HOSTS", host)
set_kv("CORS_ALLOW_ORIGIN", public_url.rstrip("/"))
root = str(env.parent).replace("\\", "/")
set_kv("WORKFRAME_HOST_COMPOSE_DIR", root)
set_kv("WORKFRAME_HOST_PROJECT_ROOT", root)
env.write_text(text, encoding="utf-8")
PY

cd "$INSTALL_DIR"
# Generated compose used to hardcode loopback APP_BASE_URL in environment (overrides .env).
if grep -q '^[[:space:]]*- APP_BASE_URL=http://127.0.0.1:' docker-compose.yml 2>/dev/null; then
  sed -i 's|^[[:space:]]*- APP_BASE_URL=http://127.0.0.1:.*$||' docker-compose.yml
fi
bash scripts/bootstrap-native.sh
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build

UI_PORT="$(grep -E '^WORKFRAME_UI_PORT=' .env | tail -n1 | cut -d= -f2- || echo 28644)"
API_PORT="$(grep -E '^WORKFRAME_API_PORT=' .env | tail -n1 | cut -d= -f2- || echo 29120)"

if [[ "$(id -u)" -eq 0 ]]; then
  HOST="${PUBLIC_URL#https://}"
  HOST="${HOST#http://}"
  HOST="${HOST%%/*}"
  if [[ -f "$PKG/scripts/setup-public-https.sh" ]]; then
    bash "$PKG/scripts/setup-public-https.sh" "$HOST" "$UI_PORT" || true
  fi
fi

echo ""
echo "Fresh VPS pack install:"
echo "  dir  $INSTALL_DIR"
echo "  UI   http://127.0.0.1:${UI_PORT}/"
echo "  API  http://127.0.0.1:${API_PORT}/api/health"
echo "  pub  ${PUBLIC_URL}"
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
    curl -fsS "http://127.0.0.1:${API_PORT}/api/health"
    echo ""
    break
  fi
  sleep 2
done
curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null || fail "API health unreachable"
ok "vps pack install complete"
