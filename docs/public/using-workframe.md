# Using Workframe

What you can do in the Workframe UI after install.

## Workspace

- **Rooms and spaces** — team channels with live message history
- **Direct messages** — human-to-human and agent DMs
- **Activity** — room-scoped feed of agent actions
- **Files** — browse and edit project files under `/workspace`; use **Select files** in Navigator to download one file with its original name, download multiple files or whole folders as a ZIP, or permanently delete a confirmed file selection
- **Browser panel** — preview text, theme-aware Markdown artifacts, CSV tables, images, audio, video, PDFs, HTML, and other workspace artifacts

## Agents

- **Team rail** — switch between agent lanes (native concierge and specialists)
- **Chat** — stream agent replies; stop or steer an active turn
- **Create agent** — add a new Hermes profile from the team rail
- **Model picker** — choose the model and fallback chain owned by that agent; the same choice applies in its DM and room mentions
- **Skills** — attach Hermes skills from the composer
- **Slash commands** — Workframe-native command palette (subset of Hermes CLI)

## Your account

- **Profile** — display name and workspace identity
- **Connect accounts** — OAuth and API keys for LLM and integration providers (BYOK)
- **Per-user runtime** — each member gets an isolated Hermes profile tree (`u-{user}-{agent}`) for credentials and chat; it follows the agent's model choice

## Team admin

- **Workspace members and invites** — add colleagues (invite-only in multi-user modes)
- **Stack-managed keys** — optional company-pays LLM keys for owner/admin
- **Hermes dashboard** — owner/admin access to the native Hermes dashboard (proxied at `/hermes-dashboard/`)

## Collaboration patterns

- **Space @mentions** — the avatar-backed picker includes both people and agents in the room; agent mentions invoke the shared live turn via SSE
- **Replies and reactions** — reply to a persisted message or add a durable emoji reaction; hovering a posted reaction shows who reacted
- **Agent DMs** — private lane per user; sessions persist per browser tab
- **Kanban** — execution state via Hermes Kanban; project truth stays in files

Advanced Hermes settings (MCP, cron, full config editor) are available in the **Hermes dashboard** for owner/admin.

Navigator selection accepts files and folders for download. A selected folder is expanded recursively into the ZIP while protected paths stay excluded. Deletion remains file-only: Workframe disables it when a folder is selected, validates the complete selection on the server before mutation, rejects protected or out-of-workspace paths, and closes Browser tabs for files that were deleted.

Images attached from chat are stored under the workspace-visible `uploads/` folder so they appear in Navigator and remain movable by an agent or teammate. Chat renders the image itself without printing its storage filename.

See [Install](./install.md), [Security](./security.md), and [Session architecture](./session-architecture.md).
