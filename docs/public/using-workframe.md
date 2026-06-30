# Using Workframe

What you can do in the Workframe UI after install.

## Workspace

- **Rooms and spaces** — team channels with live message history
- **Direct messages** — human-to-human and agent DMs
- **Activity** — room-scoped feed of agent actions
- **Files** — browse and edit project files under `/workspace`
- **Browser panel** — preview HTML and other workspace artifacts

## Agents

- **Team rail** — switch between agent lanes (native concierge and specialists)
- **Chat** — stream agent replies; stop or steer an active turn
- **Create agent** — add a new Hermes profile from the team rail
- **Model picker** — choose a model from providers you have connected
- **Skills** — attach Hermes skills from the composer
- **Slash commands** — Workframe-native command palette (subset of Hermes CLI)

## Your account

- **Profile** — display name and workspace identity
- **Connect accounts** — OAuth and API keys for LLM and integration providers (BYOK)
- **Per-user runtime** — each member gets an isolated Hermes profile tree (`u-{user}-{agent}`) for credentials and chat

## Team admin

- **Workspace members and invites** — add colleagues (invite-only in multi-user modes)
- **Stack-managed keys** — optional company-pays LLM keys for owner/admin
- **Hermes dashboard** — owner/admin access to the native Hermes dashboard (proxied at `/hermes-dashboard/`)

## Collaboration patterns

- **Space @mentions** — mention an agent in a room; all members see the live turn via SSE
- **Agent DMs** — private lane per user; sessions persist per browser tab
- **Kanban** — execution state via Hermes Kanban; project truth stays in files

Advanced Hermes settings (MCP, cron, full config editor) are available in the **Hermes dashboard** for owner/admin.

See [Install](./install.md), [Security](./security.md), and [Session architecture](./session-architecture.md).
