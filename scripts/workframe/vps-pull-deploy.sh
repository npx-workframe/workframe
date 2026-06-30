#!/usr/bin/env bash
# Deploy from local git archive tarball (private repo — VPS cannot git clone).
set -euo pipefail
TARBALL="${1:-/tmp/workframe-deploy.tar}"
PUBLIC_HOST="${2:-}"
ROOT=/opt/workframe
TARGET="${WORKFRAME_REPO_ROOT:-$ROOT/repo}"
STAMP=$(date +%Y%m%d%H%M%S)
BACKUP="$ROOT/_deploy_backup_$STAMP"

[[ -f "$TARBALL" ]] || { echo "missing tarball: $TARBALL"; exit 1; }

mkdir -p "$BACKUP"
if [[ -d "$TARGET" ]]; then
  echo "Backing up runtime, .env, dist..."
  [[ -d "$TARGET/runtime" ]] && cp -a "$TARGET/runtime" "$BACKUP/"
  [[ -f "$TARGET/infra/compose/workframe/.env" ]] && cp -a "$TARGET/infra/compose/workframe/.env" "$BACKUP/.env"
  [[ -d "$TARGET/apps/web/dist" ]] && cp -a "$TARGET/apps/web/dist" "$BACKUP/dist"
  mv "$TARGET" "${TARGET}.old.${STAMP}"
fi

mkdir -p "$TARGET"
tar -xf "$TARBALL" -C "$TARGET"
find "$TARGET/scripts/workframe" -name '*.sh' -exec sed -i 's/\r$//' {} +

if [[ -d "$BACKUP/runtime" ]]; then
  rm -rf "$TARGET/runtime"
  cp -a "$BACKUP/runtime" "$TARGET/runtime"
fi
if [[ -f "$BACKUP/.env" ]]; then
  cp -a "$BACKUP/.env" "$TARGET/infra/compose/workframe/.env"
else
  # ponytail: fall back to newest old tree if a partial deploy left no .env backup
  OLD_ENV=$(ls -1dt "${TARGET}.old."* 2>/dev/null | while read -r d; do
    [[ -f "$d/infra/compose/workframe/.env" ]] && echo "$d/infra/compose/workframe/.env" && break
  done)
  if [[ -n "${OLD_ENV:-}" ]]; then
    echo "Restoring .env from $OLD_ENV"
    cp -a "$OLD_ENV" "$TARGET/infra/compose/workframe/.env"
  fi
fi
if [[ -d "$BACKUP/dist" ]]; then
  mkdir -p "$TARGET/apps/web"
  cp -a "$BACKUP/dist" "$TARGET/apps/web/dist"
fi

node "$TARGET/scripts/workframe/ensure-compose-host-paths.mjs" --project-root "$TARGET"

cd "$TARGET"
if [[ ! -d .git ]]; then
  git init -q -b main
  git remote add origin https://github.com/npx-workframe/workframe.git 2>/dev/null || git remote set-url origin https://github.com/npx-workframe/workframe.git
fi

bash scripts/workframe/vps-deploy.sh

if [[ ! -f "$TARGET/apps/web/dist/index.html" ]]; then
  echo "ERROR: apps/web/dist/index.html still missing after vps-deploy build." >&2
  exit 1
fi

  if [[ -n "$PUBLIC_HOST" ]]; then
  echo "Setting compose public URL for $PUBLIC_HOST..."
  node scripts/workframe/set-compose-public-url.mjs "https://${PUBLIC_HOST}" \
    --env infra/compose/workframe/.env
  cd infra/compose/workframe
  docker compose up -d
  cd "$TARGET"
fi

docker restart workframe-ui >/dev/null 2>&1 || true

API_PORT=$(grep -E '^WORKFRAME_API_PORT=' infra/compose/workframe/.env | cut -d= -f2 || echo 29120)
UI_PORT=$(grep -E '^WORKFRAME_UI_PORT=' infra/compose/workframe/.env | cut -d= -f2 || echo 28644)
echo "--- health ---"
curl -s "http://127.0.0.1:${API_PORT}/api/health"
echo
curl -s -o /dev/null -w "ui:%{http_code}\n" "http://127.0.0.1:${UI_PORT}/"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
