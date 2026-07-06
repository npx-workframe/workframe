# PM runbook — edit, build, deploy

**Default:** execute these after patches without asking Alan. Repo root: `<workframe-repo>`.

**Stage gates:** Read [`docs/ledger/program-status.md`](../../docs/ledger/program-status.md) before picking work — Stage A complete; active push is **B→C→D**; **stop before Stage E** deferred items. `ledger-next.mjs` sorts by `backlog.json` `program_stages.pick_order` (WF-040).

## Four targets (never confuse)

| Target | Path | Edit? |
|--------|------|-------|
| **Source** | This repo | **Yes** — `services/workframe-api/`, `apps/web/src/` |
| **Dogfood local** | `../MyBusiness` | **No** — disposable install |
| **Dogfood VPS** | `/opt/workframe/MyBusiness` | **No** — reinstall from pack |
| **Host Hermes** | `%LOCALAPPDATA%\hermes` | **OFF LIMITS** |

## Canonical edit order

```powershell
cd <workframe-repo>
# 1. Edit services/workframe-api/ and/or apps/web/src/

# 2. If UI changed:
pnpm build:web

# 3. If API or supervisor changed:
node packages/create-workframe/scripts/sync-canonical-to-package.mjs

# 4. If UI changed:
node packages/create-workframe/scripts/bundle-workframe-ui.mjs

# 5. Dogfood preview (local MyBusiness):
#    - UI only: dist volume mount — rebuild web often enough
#    - API/supervisor: docker compose up -d --build workframe-api workframe-supervisor
#      OR Admin → Updates after npm publish
```

**Never backwards:** installer copies (`packages/create-workframe/workframe-api/`) are mirrors only.

## Dogfood local

```powershell
# Wipe + fresh install (sign-off / DR — not per bugfix)
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm

# Build + pack + wipe (pre-publish proof)
.\scripts\workframe\sign-off-install.ps1

# Pre-publish without install
.\scripts\workframe\install-gate.ps1

# After wizard: http://127.0.0.1:18644
```

**Routine fix on existing dogfood:** Admin → Updates → **Workframe** (needs ≥0.1.10 apply path). Hermes update is separate panel.

```powershell
# Manual compose refresh if needed (from MyBusiness dir):
cd ../MyBusiness
docker compose up -d --build workframe-api workframe-supervisor workframe
```

## Bump and publish

```powershell
cd <workframe-repo>
# Bump package.json (root + packages/create-workframe) — align README install @version
pnpm build:web
node packages/create-workframe/scripts/sync-canonical-to-package.mjs
node packages/create-workframe/scripts/bundle-workframe-ui.mjs
.\scripts\workframe\install-gate.ps1
# Alan sign-off: sign-off-install.ps1 + wizard + chat
.\scripts\workframe\publish-npm.ps1
git add -A ; git commit -m "..." ; git push ; git tag vX.Y.Z ; git push origin vX.Y.Z
```

**WF-001:** README and `docs/public/install.md` must match published version.

## VPS

```powershell
.\scripts\workframe\open-vps-tunnel.ps1
.\scripts\workframe\reset-vps-runtime.ps1 -VpsHost user@host
```

Verify: `bash scripts/workframe/verify-public-deploy.sh` on VPS.

## Harness

```powershell
node .harness/verify.mjs
pnpm test:ci
node scripts/workframe/ledger-next.mjs
```

## SECURE_MODE notes

- API has **no** Docker socket; supervisor holds socket
- Supervisor image rebuild after `services/workframe-supervisor/` changes (not volume-mounted in canonical compose)
- In-app Workframe update: API prefetches tarball; supervisor applies `WORKFRAME_UPDATE_TARBALL`

## What not to use

See [scripts/workframe/README.md](../../scripts/workframe/README.md) deprecated table — `infra/compose/workframe` is reference template only, not local dogfood.

## After every shipped patch

1. Update `docs/ledger/backlog.json` evidence + status
2. Update `docs/ledger/now.md` if wedge changed
3. Append `operations/log.md`
