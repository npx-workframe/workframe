# Workframe v0.1.15

| Component | Version |
|-----------|---------|
| create-workframe | 0.1.15 |
| workframe CLI | 0.1.11 (stub removed WF-038; use create-workframe) |
| @workframe/workframe | 0.1.11 (stub removed WF-038; use create-workframe) |
| Workframe API / UI | 0.1.15 (bundled in create-workframe) |

```bash
npx create-workframe@0.1.15 MyProject
```

Hermes gateway image: `nousresearch/hermes-agent:latest` (updated via stack admin).

## 0.1.15

- Shared project-room sessions across users with per-turn invitee credential overlays; DMs remain private per-user proxy sessions.
- Canonical room message IDs replace optimistic client IDs to prevent duplicated room messages.

## 0.1.14

- UI theme rebrand: `strato-dark`, `neo-light`, `neo-blue` (legacy slug migration); relief/line chrome tokens and onboarding polish.
- Onboarding wizard: `agent_model` step + CopyInput on public URL step (aligned with backend flow).

## 0.1.13

- Gate-run A–D: server.py split to ~2.6k lines + handler_modules; WF-012 build stamp; WF-016 receipt per run; WF-036 ConciergeFlow/HermesSession decompositions.
- Public repo verify: remove operator-specific paths from tracked docs/tests.

## 0.1.12

- Chat wait hints gated on active turns; fix group-room live SSE stale snapshots and batcher flush.
- Project room message cache (stale-while-revalidate) matching DM bind pattern.
- Public deploy verify: anonymous `/api/snapshot` must return 401.

## 0.1.11

- Sync all install scripts from npm pack during in-app Workframe apply.

## 0.1.10

- Defer supervisor self-restart during in-app Workframe apply (SECURE_MODE).

## 0.1.9

- Fix in-app Workframe apply on SECURE_MODE: API prefetches npm, supervisor rebuilds (control-net has no registry egress).
- Fix compose apply from supervisor on Windows (skip host-bindings when host path is not visible in-container).
- Record installed pack version in `workframe-api/data/package-version` after apply.
