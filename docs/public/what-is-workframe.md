# What is Workframe?

Workframe is a **multi-user web shell around [Hermes Agent](https://github.com/NousResearch/hermes-agent)**. It packages Hermes with auth, rooms, a file workspace, credential vault, and Docker Compose so a team can run agents on shared project files.

Workframe is **not** a Hermes fork and **not** a general-purpose chat product. It is a project starter and operations layer for agent-assisted work where **files on disk are the source of truth**.

Repository: [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe)

## Who it is for

| You areâ€¦ | Typical use |
|----------|-------------|
| **Solo developer** | One machine, one operator, local Docker â€” explore Hermes with a ready-made UI |
| **Small team** | Trusted colleagues on Docker/LAN â€” shared rooms, BYOK keys, invite-only access |
| **Operator hosting others** | HTTPS VPS, invite-only â€” public multi-user mode with hardened compose |

If you only need a single Hermes profile on your laptop with no team UI, [Hermes alone](https://hermes-agent.nousresearch.com/docs/) may be enough. Choose Workframe when you want **shared workspace, multi-user auth, and compose packaging**.

## What you get

- **Web UI** â€” chat, files, browser preview, activity feed, team rail
- **Hermes runtime** â€” profiles, skills, Kanban, gateway (via Docker image `nousresearch/hermes-agent`)
- **Workframe API** â€” sessions, rooms, vault, provider connect, Hermes proxy
- **Installer** â€” `npx create-workframe@0.1.51 MyProject` scaffolds a runnable project
- **Optional surfaces** â€” Telegram and Discord (configured per install)

## How it relates to Hermes

```text
Workframe UI  â†’  Workframe API  â†’  Hermes gateway (profiles, chat, tools)
                      â†“
                 SQLite + vault + Files/ (/workspace)
```

Workframe adds tenancy, auth, and UI around Hermes. Agent execution, skills, and Kanban semantics come from Hermes. Workframe docs assume you may need [Hermes documentation](https://hermes-agent.nousresearch.com/docs/) for advanced agent configuration.

## Core concepts

| Term | Meaning |
|------|---------|
| **Native / concierge agent** | Project-facing coordinator (`{project}-agent`) |
| **Specialist agents** | Optional role agents added when needed |
| **Lane** | UI route to an agent profile |
| **Runtime profile** | Per-user Hermes home (`u-{user}-{agent}`) for BYOK isolation |
| **Files** | Project workspace â€” canonical truth (`Files/` on host, `/workspace` in containers) |
| **Kanban** | Hermes execution state and handoffs |
| **Chat** | Intent and coordination â€” not the durable record of record |

## Two ways to use this repository

| Path | When | Start here |
|------|------|------------|
| **Install a project** | You want a running Workframe for your team | [Install](./install.md) |
| **Hack on Workframe itself** | You want to change UI, API, or installer | [Develop](./develop.md) |

Generated installs copy API/UI/supervisor from the npm package. **Source of truth for product code** is this monorepo (`apps/web`, `services/workframe-api`, etc.). See [Audit](./audit.md) for where to read before trusting a deploy.

## Version expectations

Current release line: **0.1.x** (see [VERSION.md](../VERSION.md)). Expect rough edges: wizard-driven setup, Docker-first ops, and API routes that serve the bundled UI rather than a frozen public SDK.

## Next steps

- [Prerequisites](./prerequisites.md) â€” what you need before install
- [Install](./install.md) â€” end-user setup wizard
- [Using Workframe](./using-workframe.md) â€” features after first login
- [Architecture](./architecture.md) â€” system design
- [Security](./security.md) â€” modes and credential model
- [Audit](./audit.md) â€” code review path for evaluators
