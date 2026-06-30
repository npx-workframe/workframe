#!/usr/bin/env bash
set -euo pipefail
cd "${WORKFRAME_REPO_ROOT:-/opt/workframe/repo}/infra/compose/workframe"

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s/^${key}=.*/${key}=${val}/" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

set_kv WORKFRAME_INSTALL_ID wf_vps_slot2
set_kv WORKFRAME_SLOT 2
set_kv WORKFRAME_PROJECT Workframe
set_kv WORKFRAME_GATEWAY_PORT 28642
set_kv WORKFRAME_DASHBOARD_PORT 29119
set_kv WORKFRAME_API_PORT 29120
set_kv WORKFRAME_UI_PORT 28644

grep -E '^WORKFRAME_(INSTALL|SLOT|PROJECT|GATEWAY|DASHBOARD|API|UI)' .env

docker compose down
docker compose up -d --build
sleep 4
# ponytail: gateway already starts via compose command; no separate exec needed
curl -s http://127.0.0.1:29120/api/health
echo
curl -s -o /dev/null -w 'ui:%{http_code}\n' http://127.0.0.1:28644/
docker exec workframe-api python3 -c 'import zk_auth as z; print(z.session_cookie_name())'
