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

## Harness (Cursor-owned)

Workframe operator loops are **Cursor-owned** (not ChatGPT). Scheduler ownership is documented in ABKB `operations/registry/scheduler-ownership.md`.

- Feature scenarios: `.harness/feature_list.json`
- Cloud verify: `node .harness/verify.mjs` (also `.cursor/environment.json` start command)
- Full CI parity: `pnpm test:ci`
- Install-gate (local): AB workspace `workframe-release` skill

Edit canonical source (`services/workframe-api/`, `apps/web/src/`) — not installer copies alone.
