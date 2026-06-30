# Workframe overview

Workframe is a usability and bootstrap layer on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent). It is **not** a Hermes fork and **not** a replacement orchestration engine.

Repository: [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe)

Install for end users:

```bash
npx create-workframe@0.1.2 MyProject
```

## What it provides

- A reusable project starter for semi-autonomous agent collaboration
- Multi-user rooms, spaces, DMs, and agent lanes in one web UI
- File-based project truth under `/workspace` (generated `Files/`)
- Hermes Kanban for execution state and handoffs
- Optional Telegram and Discord surfaces (configured per install)
- Docker compose stack: gateway, dashboard, workframe-api, workframe-supervisor, and UI (`workframe` service)

## Core ontology

| Concept | Role |
|---------|------|
| **Concierge / native agent** | Project-facing coordinator (`{projectName} Agent`) |
| **Specialists** | Optional role agents (visionary, architect, docs, dev, research, designer) |
| **Context planes** | Chat = intent; Kanban/session = execution; Files = canonical truth |
| **Lane** | User-visible route to an agent profile |
| **Runtime profile** | Per-user Hermes home (`u-{user}-{template}`) for BYOK and isolation |

Default topology is **native-only** at first boot. Specialists are added when recurring demand justifies them.

## Truth model

```text
1. Files     — canonical project truth (/workspace)
2. Kanban    — execution state and handoffs
3. Chat      — intent and coordination only
```

## Stack layout (monorepo)

```text
apps/web                  Product UI (Vite/React)
services/workframe-api    Python BFF
services/workframe-supervisor  Secure-mode exec broker
packages/create-workframe npm installer
packages/workframe        lifecycle CLI
infra/compose/workframe   Reference Docker stack
```

## Related docs

- [Getting started](./getting-started.md)
- [Architecture](./architecture.md)
- [Runtime operations](./runtime-operations.md)
- [Public multi-user deploy](../../infra/compose/workframe/PUBLIC_DEPLOY.md)
