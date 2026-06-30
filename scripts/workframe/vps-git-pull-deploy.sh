#!/usr/bin/env bash
# git pull deploy on VPS (requires deploy key: ~/.ssh/workframe_deploy).
set -euo pipefail
TARGET="${WORKFRAME_REPO_ROOT:-/opt/workframe/repo}"
STAMP=$(date +%Y%m%d%H%M%S)
BACKUP="/opt/workframe/_deploy_backup_$STAMP"
WORK="/opt/workframe/_git_work_$STAMP"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/workframe_deploy -o IdentitiesOnly=yes"

mkdir -p "$BACKUP"
if [[ -d "$TARGET" ]]; then
  echo "Backing up runtime, .env, dist..."
  [[ -d "$TARGET/runtime" ]] && cp -a "$TARGET/runtime" "$BACKUP/"
  [[ -f "$TARGET/infra/compose/workframe/.env" ]] && cp -a "$TARGET/infra/compose/workframe/.env" "$BACKUP/.env"
  [[ -d "$TARGET/apps/web/dist" ]] && cp -a "$TARGET/apps/web/dist" "$BACKUP/dist"
  mv "$TARGET" "${TARGET}.old.${STAMP}"
fi

git clone --depth 1 -b main git@github.com:npx-workframe/workframe.git "$WORK"
mv "$WORK" "$TARGET"
cd "$TARGET"
find scripts/workframe -name '*.sh' -exec sed -i 's/\r$//' {} +

[[ -d "$BACKUP/runtime" ]] && cp -a "$BACKUP/runtime" "$TARGET/runtime"
if [[ -f "$BACKUP/.env" ]]; then
  cp -a "$BACKUP/.env" "$TARGET/infra/compose/workframe/.env"
else
  OLD_ENV=$(ls -1dt "${TARGET}.old."* 2>/dev/null | while read -r d; do
    [[ -f "$d/infra/compose/workframe/.env" ]] && echo "$d/infra/compose/workframe/.env" && break
  done)
  if [[ -n "${OLD_ENV:-}" ]]; then
    echo "Restoring .env from $OLD_ENV"
    cp -a "$OLD_ENV" "$TARGET/infra/compose/workframe/.env"
  fi
fi
[[ -d "$BACKUP/dist" ]] && mkdir -p "$TARGET/apps/web" && cp -a "$BACKUP/dist" "$TARGET/apps/web/dist"

node scripts/workframe/ensure-compose-host-paths.mjs --project-root "$TARGET"

if [[ ! -f "$TARGET/apps/web/dist/index.html" ]]; then
  echo "Note: no cached dist — vps-deploy will build UI on server."
fi

bash scripts/workframe/vps-deploy.sh

if [[ ! -f "$TARGET/apps/web/dist/index.html" ]]; then
  echo "ERROR: apps/web/dist/index.html still missing after vps-deploy build." >&2
  exit 1
fi
docker restart workframe-ui >/dev/null 2>&1 || true

API_PORT=$(grep -E '^WORKFRAME_API_PORT=' infra/compose/workframe/.env | cut -d= -f2 || echo 29120)
curl -s "http://127.0.0.1:${API_PORT}/api/health"
echo
