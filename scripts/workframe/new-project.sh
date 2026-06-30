#!/usr/bin/env bash
# Meta repo: bundle UI + scaffold + auto-launch Phase B installer.
# Usage: ./scripts/new-project.sh BrandAuthority --out ~/projects --force
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/packages/create-workframe/scripts/new-project.mjs"
if [[ ! -f "$SCRIPT" ]]; then
  echo "Missing $SCRIPT — run from the Workframe meta repo." >&2
  exit 1
fi
exec node "$SCRIPT" "$@"
