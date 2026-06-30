# AGENTS — {projectName}

Shared project workspace (`/workspace` → `/opt/data/workspace`). Hermes mounts host `Files/` at `/opt/data/workspace`; `/workspace` is a symlink so writes pass `HERMES_WRITE_SAFE_ROOT`.

## Native agent

**{nativeAgentName}** (`{nativeProfileSlug}`) — concierge and orchestrator. Chat via `../scripts/chat.sh` or `../scripts/chat.ps1`, or browser `/chat` after Phase B.

## Layout

| Path | Role |
|------|------|
| `Files/` (here) | Project source of truth — keep lean until you add real work |
| `Agents/` | Hermes runtime — profiles, skills, memory (never commit) |

## Rules

- Do not use Hermes `default` profile for project work.
- Put deliverables here; keep Workframe/Hermes doctrine in agent SOUL under `Agents/profiles/`.
- **Credentials never in chat** — API keys and bot tokens go through Hermes setup, dashboard, or Workframe secure UI only.
- **{nativeAgentName}** is the PM/concierge — cross-lane work routes through them unless you are bound to a dedicated Discord/TG channel for this profile.
- Outcomes live in `/workspace` (this folder); chat is intake, not the system of record.
