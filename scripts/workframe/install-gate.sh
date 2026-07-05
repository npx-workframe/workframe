#!/usr/bin/env bash
# Installer sign-off gate — canonical source → pack.
# Dogfood install = reset-dogfood-docker.ps1 (npx create-workframe only), not this script.
# Usage: bash scripts/workframe/install-gate.sh [--quick]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$ROOT/packages/create-workframe"
QUICK=0
if [[ "${1:-}" == "--quick" ]]; then
  QUICK=1
fi

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

cd "$ROOT"

ok "building web"
pnpm build:web

ok "syncing API/supervisor to installer package"
node "$PKG/scripts/sync-canonical-to-package.mjs"

ok "bundling UI into installer package"
node "$PKG/scripts/bundle-workframe-ui.mjs"

ok "API tests"
pnpm test:api

ok "installer scaffold tests"
pnpm test:scaffold

ok "npm pack"
PACK_TGZ="$(npm pack "$PKG" --pack-destination "$ROOT/.install-gate" 2>/dev/null | tail -n1)"
[[ -f "$ROOT/.install-gate/$PACK_TGZ" ]] || fail "npm pack did not produce tarball"

for path in package/scripts/lib/install-identity.mjs package/scripts/bootstrap-workspace-link.sh; do
  tar -tzf "$ROOT/.install-gate/$PACK_TGZ" | grep -q "$path" || fail "pack missing $path"
done
if tar -xOf "$ROOT/.install-gate/$PACK_TGZ" package/scripts/bootstrap-workspace-link.sh | grep -q $'\r'; then
  fail "pack bootstrap-workspace-link.sh has CRLF (Alpine sh will fail)"
fi
ok "pack contains installer scripts (LF shell scripts)"

ok "install gate passed"
