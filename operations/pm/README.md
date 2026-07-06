# Workframe PM — operating system

**Role:** Project Manager for `npx-workframe/workframe`  
**Reports to:** Alan → AIbert (Orchestrator) → CEO (future)  
**Canonical home:** this folder (source repo). ABKB mirrors: `abkb/operations/roles/pm-workframe/`

## Every Workframe session starts here

```text
1. operations/pm/session.md              — boot checklist (60 seconds)
2. docs/ledger/program-status.md         — verified stage gates (A→D); prefer over stale backlog rows
3. docs/ledger/backlog.json              — machine queue (WF-*); program_stages from WF-040
4. docs/ledger/now.md                    — shipping wedge context
5. node scripts/workframe/ledger-next.mjs — next item by stage order B→C→D
```

## Files in this harness

| File | Purpose |
|------|---------|
| [identity.md](identity.md) | PM authority, boundaries, escalation |
| [session.md](session.md) | Boot order every run |
| [runbook.md](runbook.md) | Edit, build, dogfood, bump, publish, compose — **no asking** |
| [composition.md](composition.md) | ABKB + Architectonic + spec-kit + ledger wiring |
| [queues.json](queues.json) | Active handoffs (WF-* ↔ workers) |
| [status.json](status.json) | PM heartbeat |

## Ledgers (one train, many cars)

```text
docs/ledger/backlog.json     program queue (WF-*)     ← PM owns priority
.harness/feature_list.json   verify scenarios         ← tests role
operations/pm/queues.json    this-session handoffs    ← PM → worker
operations/log.md            narrative                ← append-only
operations/release-evidence/ maintainer sign-off JSON schemas (WF-003)
abkb/.../queues.json         cross-portfolio assign   ← optional sync
```

## Workers (ABKB personas)

| backlog `owner_role` | ABKB role id | Action |
|----------------------|--------------|--------|
| implementer | `coder` | Patch + PR |
| reviewer | `code-reviewer` | Review → done/todo |
| harness | `tests` | Scripts, verify, gates |
| docs | `docs` | Public docs, ledger prose |
| design | `designer` | UX, in-app copy, shadcn UI (`apps/web/src/`) |

PM **may implement** when Alan assigns direct execution in chat — still update `backlog.json`.

## Skills (do not re-read every time — runbook has commands)

- `workframe-release` — publish loop
- `ab-project-routing` — repo root

## Archive policy

Planning superseded by backlog → `archive/`. Do not add new planning rails outside `docs/ledger/specs/<WF-ID>/`.
