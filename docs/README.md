# Workframe documentation

Documentation for [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe).  
Also published at [docs.workfra.me](https://docs.workfra.me).

## Ledger (start here for status)

| Doc | |
|-----|---|
| [Ledger index](ledger/README.md) | Now, north star, audits, loop engineering |
| [Now](ledger/now.md) | Current shipping wedge |
| [North star summary](ledger/north-star.md) | Vision + link to full strategy brief |
| [Audit registry](ledger/audits.md) | All audits with status |
| [Backlog (JSON)](ledger/backlog.json) | Machine queue — 17 findings + north-star + 0027 |
| [Agent automation](ledger/automation.md) | Implementer/reviewer loop protocol |
| [Spec-kit mapping](ledger/spec-kit.md) | Spec-driven dev integration |
| [Strategy brief](strategy/README.md) | Full v0.1.1 north-star package |

## Start here

| I want to… | Read |
|------------|------|
| **Understand what this is** | [What is Workframe?](public/what-is-workframe.md) |
| **Install for my team** | [Prerequisites](public/prerequisites.md) → [Install](public/install.md) |
| **Review security before deploy** | [Security](public/security.md) → [Audit guide](public/audit.md) |
| **Hack on the product** | [Develop](public/develop.md) → [Contributing](public/contributing.md) |
| **Run a public VPS** | [PUBLIC_DEPLOY.md](../infra/compose/workframe/PUBLIC_DEPLOY.md) |

## Product

| Doc | |
|-----|---|
| [What is Workframe?](public/what-is-workframe.md) | Audience, concepts, Hermes relationship |
| [Prerequisites](public/prerequisites.md) | Docker, SMTP, keys, deployment modes |
| [Install](public/install.md) | `npx create-workframe`, wizard, generated layout |
| [Using Workframe](public/using-workframe.md) | Features in the UI |
| [Operations](public/operations.md) | Services, updates, backup, troubleshooting |

## Design and trust

| Doc | |
|-----|---|
| [Architecture](public/architecture.md) | Components, volumes, credentials |
| [Security](public/security.md) | Modes, vault, multi-user controls |
| [Audit guide](public/audit.md) | Code review path for evaluators |
| [Deploy on a VPS](../infra/compose/workframe/PUBLIC_DEPLOY.md) | HTTPS multi-user checklist |
| [Report a vulnerability](../SECURITY.md) | Responsible disclosure |

## Reference

| Doc | |
|-----|---|
| [Sessions and chat](public/session-architecture.md) | How chat sessions bind to Hermes |
| [API reference](public/api-reference.md) | HTTP routes used by the UI |
| [Database schema](public/schema.sql) | SQL schema |

## Contributors

| Doc | |
|-----|---|
| [Develop](public/develop.md) | Monorepo setup |
| [Contributing](public/contributing.md) | Issues, PRs, code areas |
| [Release verification](public/release.md) | Pre-publish regression scripts |
| [Version map](VERSION.md) · [Licensing](LICENSING.md) | Releases and legal |

## Workspace guides (installer)

Copied into generated projects via `create-workframe`:

- [Onboarding](../packages/create-workframe/docs/workspace-instructions/WORKFRAME_ONBOARDING.md)
- [Kanban](../packages/create-workframe/docs/workspace-instructions/WORKFRAME_KANBAN.md)
- [Routing](../packages/create-workframe/docs/workspace-instructions/WORKFRAME_ROUTING.md)
- [Documents & artifacts](../packages/create-workframe/docs/workspace-instructions/WORKFRAME_DOCUMENTS_AND_ARTIFACTS.md)
- [Telegram](../packages/create-workframe/docs/workspace-instructions/WORKFRAME_TELEGRAM.md)
- [Discord](../packages/create-workframe/docs/workspace-instructions/WORKFRAME_DISCORD.md)

## Legacy paths

- [Overview](public/overview.md) → [What is Workframe?](public/what-is-workframe.md)
- [Getting started](public/getting-started.md) → [Install](public/install.md) / [Develop](public/develop.md)
- [Runtime operations](public/runtime-operations.md) → [Operations](public/operations.md)
