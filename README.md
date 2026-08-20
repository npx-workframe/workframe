# Workframe

**A self-hosted, multi-user workspace for agent-assisted projects.** Workframe adds authentication, rooms, shared files, credential isolation, activity records, and deployment tooling around [Hermes Agent](https://github.com/NousResearch/hermes-agent).

> **Status:** experimental, pre-1.0. The complete Workframe cell is on the `0.1.x` release line. The standalone local-link CLI is a separate `0.2.x` package surface.

[What it is](docs/public/what-is-workframe.md) Â· [Install](docs/public/install.md) Â· [Security](docs/public/security.md) Â· [Audit](docs/public/audit.md) Â· [Develop](docs/public/develop.md)

## Choose the right entry point

| Command | Purpose | Current boundary |
| --- | --- | --- |
| `npx workframe@0.2.2` | Inspect local agent runtimes and model-provider configuration. | Read-only discovery by default. An optional provider test is offered through a consent prompt; use `--no-test` or `--json` to skip interactive testing. |
| `npx create-workframe@0.1.57 MyProject` | Scaffold a complete Workframe + Hermes project cell. | UI, API, supervisor, Docker Compose, project files, profiles, and guided onboarding. |

The two packages are complementary but not interchangeable: `workframe` is the adaptive local entrypoint; `create-workframe` installs the full collaboration environment.

## Quick start: complete cell

```bash
npx create-workframe@0.1.57 MyProject
cd MyProject
```

Continue with the generated instructions and the [installation guide](docs/public/install.md). A generated cell contains the application services, project `Files/`, Hermes profiles, and the deployment manifest needed to run locally or on a controlled Docker/VPS host.

## What the full Workframe cell provides

- **Web workspace** â€” chat, files, browser preview, activity, team and agent surfaces.
- **Multi-user access** â€” authentication, invites, workspace roles, rooms, and direct messages.
- **Hermes runtime** â€” profiles, skills, sessions, Kanban, tools, and gateway execution.
- **Credential isolation** â€” encrypted vault references and short-lived per-run leases.
- **Authority and evidence** â€” run gates, append-only run events, payer/funding context, and receipts.
- **Secure operations** â€” Docker Compose packaging and a supervisor boundary for sensitive lifecycle actions.

## Architecture

```text
Workframe UI
    â”‚  /api/*
    â–¼
Workframe API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º Hermes gateway
    â”‚                              â”‚
    â”œâ”€ auth / rooms / runs         â”œâ”€ profiles / sessions / skills
    â”œâ”€ files / provider connect    â”œâ”€ chat / tools / Kanban
    â””â”€ credential vault            â””â”€ project execution
    â”‚
    â–¼
Workframe supervisor
```

Workframe does not fork or replace Hermes. It supplies the multi-user product, authority, credential, and deployment layers around it.

## Truth model

```text
Files > Kanban > Chat
```

- **Files** contain durable project truth.
- **Kanban and run records** track execution and handoffs.
- **Chat** coordinates intent; it is not the canonical project record.

## Deployment modes

| Mode | Typical use |
| --- | --- |
| `single_user_local` | One operator exploring a local cell. |
| `trusted_team` | Invite-only colleagues on a controlled Docker/LAN deployment. |
| `public_multi_user` | Hardened HTTPS/VPS deployment with explicit operational evidence. |

Review the [security model](docs/public/security.md), [audit path](docs/public/audit.md), and public-deploy documentation before exposing a cell outside a trusted network.

## Repository layout

```text
apps/web                       Vite/React product UI
services/workframe-api         API, auth, rooms, vault, runs, Hermes proxy
services/workframe-supervisor  Secure lifecycle and execution boundary
packages/create-workframe      Full-cell npm scaffolder
packages/workframe             Standalone local-link CLI
infra/compose/workframe        Reference Docker Compose deployment
scripts/workframe              Development, release, and verification tooling
docs/public                    User, operator, evaluator, and contributor docs
docs/ledger                    Current state, backlog, gates, and audit registry
```

## Develop

Use the source monorepo when changing Workframe itself. Generated installations contain packaged copies; they are not the canonical product source.

```powershell
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
```

Start with [Develop](docs/public/develop.md) and the [repository documentation index](docs/README.md).

## Maturity and claims

A passing source test or local scaffold is not public-deployment evidence. Release and deployment claims should remain tied to the exact package, commit, installed artifact, browser/runtime proof, and recovery evidence recorded in `docs/ledger/`.

The standalone CLIâ€™s current consent and provider-output verification findings are recorded in [`docs/ledger/audits/2026-07-27-monday-hard-findings.md`](docs/ledger/audits/2026-07-27-monday-hard-findings.md).

## License

Apache-2.0 â€” see [`LICENSE`](LICENSE) and [`SECURITY.md`](SECURITY.md).
