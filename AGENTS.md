# Agent Instructions

These instructions apply to AI assistants working in this repository.

**Start here:** [START_HERE.md](START_HERE.md) — project map, ledger, pitfalls, cascade read order.

## Developer loop (source → dogfood → npm)

1. **Edit source** — `services/workframe-api/`, `apps/web/src/` (not `MyBusiness/`, not installer mirrors).
2. **Dogfood preview** — build, sync installer, restart local `MyBusiness` Docker to see it live.
3. **Publish** — bump, sync, bundle, `npm publish`; new installs get it.

Full commands and anti-patterns: Cursor skill `workframe-release` (`.cursor/skills/workframe-release/SKILL.md`).

## Source Hierarchy

1. Primary source artifacts in this repository.
2. Current user instruction.
3. Verified project documentation.
4. Derived summaries.
5. Inference.
6. Speculation.

Lower levels must not override higher levels.

## Core Rules

- Evidence before inference.
- Learn the repository ontology before imposing patterns.
- Read before writing.
- Explicit uncertainty before confident guessing.
- Root causes before workarounds.
- Simplicity before complexity.
- Source artifacts over memory.
- Truth before agreement.

## Mutation Discipline

Before mutating anything:

1. Verify the exact target repository and path.
2. Read the current state or nearest existing pattern.
3. Make the smallest coherent change.
4. Read back the result.
5. Report evidence that the change landed where intended.

## Monorepo Doctrine

- Start small.
- Keep boundaries canonical.
- Add surfaces only when the product requires them.
- Never let framework choice define ontology.
- Never duplicate business rules across apps.
- Make backend authority explicit.
- Make contracts typed.
- Make deployment surfaces separate.
- Make shared packages boring and stable.

## Boundary Rules

- `apps/` contains deployable or shippable surfaces.
- `packages/` contains shared product logic imported by apps.
- `infra/` contains local and production deployment definitions.
- `scripts/` contains repository automation.
- `docs/` contains durable architecture memory.

Do not place product rules inside UI apps when they belong in `packages/domain`.
Do not place transport-specific request shapes inside domain entities when they belong in `packages/contracts`.
Do not duplicate auth/session logic across clients when it belongs in `packages/auth` and `packages/sdk`.

## Harness (Cursor-owned)

Workframe operator loops are **Cursor-owned** (not ChatGPT). Scheduler ownership is documented in ABKB `operations/registry/scheduler-ownership.md`.

- Feature scenarios: `.harness/feature_list.json`
- Cloud verify: `node .harness/verify.mjs` (also `.cursor/environment.json` start command)
- Full CI parity: `pnpm test:ci`
- Install-gate (local): AB workspace `workframe-release` skill

Edit canonical source (`services/workframe-api/`, `apps/web/src/`) — not installer copies alone.

## Cursor Cloud specific instructions

Local dev runs the two active surfaces directly (no Docker needed for UI/API iteration).
The reference `docker compose` stack in `docs/public/develop.md` is the production-style path and
requires Docker; it is not needed to develop `apps/web` + `services/workframe-api`.

### Services and standard commands

- `apps/web` (Vite/React UI): dev server via `pnpm dev:web` (root) → serves on `localhost:5173` and binds
  only to `localhost` (use `localhost`, not `127.0.0.1`). Lint `pnpm --filter @workframe/web lint`,
  build `pnpm build:web`. Vite proxies `/api` → the API (see `apps/web/vite.config.ts`, default target
  port `18644`).
- `services/workframe-api` (stdlib Python HTTP server): run `python3 server.py`. Typecheck/build are just
  `py_compile` (`pnpm --filter @workframe/workframe-api typecheck`). Deps: `cryptography`, `PyYAML`.

### Non-obvious caveats for running the API locally

- The API defaults to non-writable data paths (`/app/data`, `/opt/data`). You MUST override:
  `WORKFRAME_API_DATA_DIR=<writable>` and `HERMES_DATA=<writable>`. Otherwise import/startup fails with
  `PermissionError: /app`.
- Set `DEV_LOCAL_UNSAFE=true` for local dev: OTP login codes are returned in the API response and shown
  on the login screen (no SMTP needed). `SECURE_MODE` and `DEV_LOCAL_UNSAFE` are mutually exclusive.
- Run the API on the port the Vite proxy targets. Simplest: `PORT=18644` (matches the vite default), or
  set `VITE_WORKFRAME_UI_PORT` to the API port.
- IMPORTANT redirect gotcha: `apps/web` `SetupAuthGate` fetches `/api/meta` and, if the browser host
  differs from `app_base_url`, redirects the browser to `app_base_url` (default `http://127.0.0.1:18644`).
  For Vite dev, start the API with `APP_BASE_URL=http://localhost:5173` so the SPA stays on the dev server.
- The login screen only appears once the install window is closed: set `"install_complete": true` in
  `<WORKFRAME_API_DATA_DIR>/stack_config.json` (otherwise the app forces the install/onboarding wizard).
  Fresh users still land on a per-user "Set up Workframe" onboarding wizard after login; completing it
  (e.g. "Just me on this machine") needs `single_user_local` deployment mode.

Example local run (from repo root):

`WORKFRAME_API_DATA_DIR=/tmp/wf/data HERMES_DATA=/tmp/wf/hermes DEV_LOCAL_UNSAFE=true APP_BASE_URL=http://localhost:5173 HOST=127.0.0.1 PORT=18644 python3 services/workframe-api/server.py`

then `pnpm dev:web`.

### Tests / lint status

- `apps/web` lint currently reports pre-existing errors (unrelated to setup); the command itself runs.
- API self-checks are standalone scripts (`services/workframe-api/test_*.py`), run with
  `python3 <file>` and the writable data-dir env vars above. A couple import `server` and exercise the
  SQLite DB, which is only created by `main()`, so they can fail standalone with `no such table`.
