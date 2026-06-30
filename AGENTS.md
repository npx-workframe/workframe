# Agent Instructions

These instructions apply to AI assistants working in this repository.

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

## Cursor Cloud specific instructions

Durable, non-obvious notes for running this repo in the Cloud Agent VM (Node 22, pnpm 10, Python 3.12 preinstalled; **no Docker**).

### Install / dependencies
- **Root `pnpm install` currently fails**: `packages/workframe-core` declares `@monorepo/tsconfig@workspace:*`, but `tooling/tsconfig` and `tooling/eslint-config` are README-only placeholders with no `package.json`. Do not rely on the root pnpm workspace.
- Install the runnable surfaces per-app via their own `package-lock.json` instead. The startup update script runs `npm install --prefix apps/web`. Other npm apps (`apps/website`, `apps/desktop`) install the same way if needed.
- The Python API (`services/workframe-api`) only needs `cryptography>=41` and `PyYAML>=6`, which are already present in the system Python — no pip step required.

### Core dev surfaces (what runs without Docker)
- **`apps/web`** — Vite/React SPA. Dev: `npm run dev` (binds `localhost:5173`). Lint: `npm run lint` (note: currently reports ~90 pre-existing source errors — not an env problem). Build: `npm run build` → `dist/`.
- **`services/workframe-api`** — Python BFF (stdlib `http.server`). Run with `python3 server.py`.
- Vite proxies `/api` to `VITE_WORKFRAME_API_PORT` (default `18644`). When running the API on `19120`, start the web app as `VITE_WORKFRAME_API_PORT=19120 npm run dev`.

### Running the API outside Docker (gotchas)
- Both `server.py` and `zk_auth.py` default their data dir to `/app` (the container path). **You must set `WORKFRAME_API_DATA_DIR`** (and `HERMES_DATA`, `WORKSPACE`) to writable paths or startup fails with `PermissionError: /app`. Use the gitignored `runtime/` dirs, e.g.:
  - `WORKFRAME_API_DATA_DIR=/workspace/runtime/workframe-api-data HERMES_DATA=/workspace/runtime/Agents WORKSPACE=/workspace/runtime/Files`
- `DEV_LOCAL_UNSAFE=true` runs the API in dev mode (no secure-mode secrets) and returns the OTP dev code in `/api/auth/start` responses (the UI shows it as a "Dev code"). `SECURE_MODE` and `DEV_LOCAL_UNSAFE` are mutually exclusive; neither set defaults to secure mode.
- `WORKFRAME_DEPLOYMENT_MODE=single_user_local` enables `/api/auth/local-bootstrap` ("Just me on this machine"), which creates the owner account with no email/SMTP.

### Hermes / full stack (needs Docker — unavailable here)
- The full product (agent chat) is the Docker Compose stack in `infra/compose/workframe` built on the external `nousresearch/hermes-agent` image plus an LLM provider. This cannot run without Docker, so live agent chat and the final onboarding "Launch Workframe" step (`bootstrap_agent_dm_lane`) are not reproducible in this VM.
- The web UI has a first-run install gate that polls `/api/install/status` and blocks until a Hermes profile exists. To reach the UI sign-in/onboarding without Docker, seed a marker profile (gitignored) so `hermes_present` flips true:
  - `mkdir -p runtime/Agents/profiles/workframe-agent && printf 'name: workframe-agent\n' > runtime/Agents/profiles/workframe-agent/profile.yaml`
- With the gate cleared, choosing **"Just me on this machine"** completes owner account creation and the authenticated multi-step setup wizard end-to-end (everything except the final Hermes launch).
