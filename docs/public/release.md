# Release verification

Scripts and checks run before publishing a new `create-workframe` version or signing off an install. For day-to-day development, see [Develop](./develop.md).

## CI parity (monorepo)

From repository root:

```bash
pnpm test:ci
```

This matches GitHub Actions: public-repo verify, API `py_compile` typecheck, web build, UI bundle copy, and scaffold smoke tests.

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

```powershell
.\scripts\workframe\sign-off-install.ps1
```

Build/sync/pack only (no install):

```powershell
.\scripts\workframe\install-gate.ps1
```

Dogfood reset only:

```powershell
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
```

Then complete the **wizard in the browser** and send a test chat. Set `dogfood-install-gate` to `passes: true` in `.harness/feature_list.json`, then:

```bash
node scripts/workframe/verify-release-gates.mjs
```

CI green alone is not sign-off. `publish-npm.ps1` calls the release-gates verifier and fails closed when local evidence is missing.

DevOps map: [scripts/workframe/README.md](../../scripts/workframe/README.md)

## Release evidence (maintainer)

Machine-readable sign-off artifacts — **not** the public security audit. Three types:

| Type | Purpose |
|------|---------|
| `PackageInstallEvidence` | Pack → clean install, file parity |
| `FirstRunEvidence` | Docker boot, wizard, first chat |
| `NegativeInstallEvidence` | Deny paths, no filesystem mutation |

Schemas and examples: [operations/release-evidence/README.md](../../operations/release-evidence/README.md)

```bash
node scripts/workframe/validate-release-evidence.mjs
```

Runners that emit live JSON:

```bash
node scripts/workframe/run-package-install-evidence.mjs --build
```

First-run and negative runners (WF-019–WF-020) are not wired yet.

## GitHub → npm (trusted publishing)

No laptop OTP after one-time setup.

### npm (each package)

On [npmjs.com](https://www.npmjs.com), for **workframe**, **create-workframe**, and **@workframe/workframe**:

1. Package → **Settings** → **Trusted publishing**
2. **GitHub Actions** → repository `npx-workframe/workframe`, workflow filename `publish-npm.yml`
3. Save (repeat per package; same workflow name)

Optional hardening after first green CI publish: **Publishing access** → require 2FA and disallow tokens.

### GitHub

1. Repo **Settings** → **Secrets and variables** → **Actions**
2. Secret `VERIFY_PUBLIC_PATTERNS_JSON` = full JSON from `scripts/workframe/verify-public-patterns.local.json` (gitignored operator denylist)

### Release

Bump versions in all three publish `package.json` files, commit, tag, push:

```bash
git tag v0.1.7
git push origin main
git push origin v0.1.7
```

Workflow `.github/workflows/publish-npm.yml` runs install-gate (quick), then `npm publish` via OIDC.

Local publish (OTP or granular bypass token) remains: `.\scripts\workframe\publish-npm.ps1`

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
