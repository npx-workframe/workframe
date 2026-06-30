#!/usr/bin/env bash
# VPS bootstrap — public_multi_user with TLS-ready env (run on fresh Ubuntu host).
set -euo pipefail

DOMAIN="${1:-}"
ADMIN_EMAIL="${2:-}"
if [[ -z "$DOMAIN" || -z "$ADMIN_EMAIL" ]]; then
  echo "Usage: $0 <domain> <admin@email.com>" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_DIR="${ROOT}/infra/compose/workframe"
ENV_FILE="${COMPOSE_DIR}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "${ENV_FILE}.example" "$ENV_FILE"
fi

bash "${ROOT}/scripts/workframe/setup-supervisor.sh" "$ENV_FILE"

python3 - <<'PY' "$ENV_FILE" "$DOMAIN" "$ADMIN_EMAIL"
import re, secrets, sys
from pathlib import Path
env_path = Path(sys.argv[1])
domain, email = sys.argv[2], sys.argv[3]
text = env_path.read_text(encoding="utf-8")
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
set_kv("APP_BASE_URL", f"https://{domain}")
set_kv("ALLOWED_HOSTS", domain)
set_kv("CORS_ALLOW_ORIGIN", f"https://{domain}")
set_kv("EMAIL_FROM", email)
import base64
for k in ("ZK_AUTH_HMAC_KEY", "ZK_AUTH_SESSION_SECRET", "WORKFRAME_API_TOKEN"):
    if not re.search(rf"^{k}=.+", text, re.M):
        set_kv(k, secrets.token_hex(32))
if not re.search(r"^ZK_AUTH_ENCRYPTION_KEY=.+", text, re.M):
    set_kv("ZK_AUTH_ENCRYPTION_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
env_path.write_text(text, encoding="utf-8")
PY

echo "Building web UI..."
(cd "$ROOT" && pnpm build:web)

echo "Starting stack (public overlay)..."
cd "$COMPOSE_DIR"
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build

echo "Done. Open https://${DOMAIN} (configure TLS reverse proxy in front of WORKFRAME_UI_PORT)."
