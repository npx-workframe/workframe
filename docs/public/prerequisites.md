# Prerequisites

What you need before installing or developing Workframe.

## Everyone

| Requirement | Notes |
|-------------|--------|
| **Docker** | Compose v2; Linux or Docker Desktop on macOS/Windows |
| **Node.js ≥ 20** | For `npx create-workframe` and lifecycle scripts |
| **LLM provider key(s)** | Each user connects their own keys by default (BYOK); admin can opt into company-pays |
| **Disk** | `Agents/` (Hermes state) and `Files/` (project workspace) grow with use |

Recommended RAM: **4 GB+** for the full stack (gateway + API + UI + supervisor).

## Solo local (`single_user_local`)

- Loopback access (`http://127.0.0.1:…`)
- No SMTP required — dev OTP may appear on the sign-in screen when SMTP is unset and `DEV_LOCAL_UNSAFE=false`
- No public domain

## Team on Docker/LAN (`trusted_team`)

- SMTP **or** local dev shortcuts
- Email for invite and sign-in codes when SMTP is configured
- Optional: GitHub OAuth app (homepage + callback URL) if you want GitHub sign-in

## Public HTTPS (`public_multi_user`)

All of the above, plus:

| Requirement | Why |
|-------------|-----|
| **Domain + HTTPS** | Boot fails without `APP_BASE_URL=https://…` |
| **SMTP** | OTP and invites (no dev OTP on public URLs) |
| **Generated secrets** | Vault KEK, proxy token, supervisor token, zk-auth keys — see [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) |
| **VPS or cloud host** | Linux recommended; scripts assume bash |

Do **not** expose `DEV_LOCAL_UNSAFE`, `WORKFRAME_E2E=1`, or install-window test flags on a public URL.

## Optional integrations

Configure during or after install wizard:

| Integration | Admin setup | Per-user |
|-------------|-------------|----------|
| **GitHub OAuth** | OAuth app client id/secret | Connect account |
| **Google / Discord / Telegram sign-in** | OAuth or bot tokens in wizard | — |
| **GitHub, Vercel, Netlify (agents)** | — | User-only; no workspace key fallback |
| **Telegram / Discord (rooms)** | Bot tokens in wizard | — |

## Hermes familiarity

Not required for install, but helpful for:

- Editing agent SOUL/skills under `Agents/profiles/`
- Kanban workflows
- Hermes dashboard (owner/admin) at `/hermes-dashboard/`

## Developers (monorepo)

Additional requirements:

| Tool | Purpose |
|------|---------|
| **pnpm** | Monorepo install and `pnpm build:web` |
| **Python 3** | Local API development (`services/workframe-api`) |
| **git** | Clone [npx-workframe/workframe](https://github.com/npx-workframe/workframe) |

See [Develop](./develop.md).

## Checklist by goal

**Try it locally:** Docker, Node, one LLM key → [Install](./install.md)

**Deploy for a team on a VPS:** Docker, domain, HTTPS, SMTP, secrets → [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md)

**Evaluate security before deploy:** [Security](./security.md) → [Audit](./audit.md)

**Contribute code:** [Develop](./develop.md) → [Contributing](./contributing.md)
