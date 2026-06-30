#!/usr/bin/env bash
# Installer sign-off gate — canonical source → pack → scaffold smoke.
# The product is create-workframe; dogfood/VPS installs are disposable sandboxes.
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

if [[ "$QUICK" -eq 0 ]] && [[ -f "$ROOT/infra/compose/workframe/.env" ]]; then
  if bash "$ROOT/scripts/workframe/verify-public-deploy.sh" "$ROOT/infra/compose/workframe"; then
    ok "verify-public-deploy"
  else
    fail "verify-public-deploy failed (stack may be down or misconfigured)"
  fi
else
  ok "skipping verify-public-deploy (--quick or no compose .env)"
fi

ok "install gate passed"
