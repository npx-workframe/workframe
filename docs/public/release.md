# Release verification

Scripts and checks run before publishing a new `create-workframe` version or signing off an install. For day-to-day development, see [Develop](./develop.md).

## Scaffold regression

From repository root:

```bash
node packages/create-workframe/scripts/test-scaffold.mjs
```

Expected: scaffold tests pass for `native`, `core`, `product`, `engineering`, and `vanilla` packs.

## Generated project smoke

```bash
node packages/create-workframe/scripts/new-project.mjs SmokeDemo --out /tmp --force
cd /tmp/SmokeDemo
docker compose up -d
node scripts/workframe.mjs doctor
```

Expected: UI loads, `/hermes-dashboard/` loads, API health OK, native SOUL present.

After Hermes setup in the generated project:

```bash
./scripts/bootstrap-native.sh
./scripts/verify-bootstrap.sh
```

Expected: `Agents/SOUL.md`, `Agents/profiles/{slug}-agent/SOUL.md`, `terminal.cwd` → `/workspace`.

## Session routing sanity

Via the API:

- same profile + different `client_id` → different sessions
- same profile + same `client_id` → same persisted session

## Specialist lifecycle

```bash
node scripts/agent-lifecycle.mjs create --slug qa-proof --display-name "QA Proof" --role "Smoke-test child"
node scripts/agent-lifecycle.mjs delete --slug qa-proof
```

## Public deploy preflight

```bash
bash scripts/workframe/verify-public-deploy.sh
```

With a configured public overlay and `WORKFRAME_DEPLOYMENT_MODE=public_multi_user`. See [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md).

## Install gate

Full sign-off before npm publish:

```bash
bash scripts/workframe/install-gate.sh   # Windows: install-gate.ps1
```

## Install-window test flags

Use only on loopback or dedicated test stacks — never on a public URL.

| Flag | Use |
|------|-----|
| `WORKFRAME_E2E=1` | Loopback, install window only |
| `WORKFRAME_E2E_UNSAFE=1` | CI/local test stacks |
| `DEV_LOCAL_UNSAFE=true` | Trusted local operators only |

OTP-in-JSON exposure stops after install completes.

## Canonical sync before pack

1. Edit `apps/web/src/` and/or `services/workframe-api/`
2. `pnpm build:web` if UI touched
3. `node packages/create-workframe/scripts/sync-canonical-to-package.mjs` if API/supervisor touched
4. `node packages/create-workframe/scripts/bundle-workframe-ui.mjs` if UI touched
5. Rebuild Docker API/supervisor images and re-run checks above

If docs disagree with code, code wins.
