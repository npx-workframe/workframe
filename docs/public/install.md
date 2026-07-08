# Install Workframe

End-user path: scaffold a project, run Docker, complete the setup wizard.

```bash
npx create-workframe@0.1.14 MyProject
cd MyProject
node scripts/workframe.mjs doctor   # optional preflight
docker compose up -d --build
```

Open the URL printed by the wizard or shown in `docker compose` output (typically `http://127.0.0.1:<ui-port>/`). Use **`127.0.0.1`**, not `localhost`, for stable session cookies on local installs.

## Install target (v0.1.x release scope)

`create-workframe` scaffolds into an **empty** target directory. If the project folder already exists, the CLI denies unless you pass `--force` (overwrite of a validated scaffold path only).

Release evidence (`NegativeInstallEvidence`) proves deny paths do **not** mutate foreign directories. Until `CellAuthorityGate` exists, treat **empty-target create** as the only supported install claim — not update-in-place or adopt-existing-cell flows.

```bash
npx create-workframe@0.1.14 MyProject    # MyProject/ must not exist yet
```

## Generated project layout

```text
MyProject/
├── Agents/                 Hermes profiles and runtime state
├── Files/                  Project workspace (/workspace in containers)
├── scripts/                Bootstrap, lifecycle, workframe.mjs CLI
├── docker-compose.yml
├── workframe-api/
├── workframe-ui/
├── workframe-supervisor/
└── workframe-manifest.json
```

The npm package copies built API, UI, and supervisor into your project. To change Workframe product code, work in the [monorepo](./develop.md) and publish/sync a new package version.

## Lifecycle CLI

From the project root:

```bash
node scripts/workframe.mjs doctor    # health checks
node scripts/workframe.mjs setup     # guided setup helpers
```

If the `workframe` npm package is installed globally:

```bash
npx workframe doctor
npx workframe setup
```

## Setup wizard (first boot)

On first visit, the UI walks through setup. Steps depend on deployment mode.

### Owner / first admin

1. **Welcome** — choose who will use this install:
   - *Just me on this machine* → `single_user_local`
   - *My team on Docker* → `trusted_team`
   - *Public on the web* → `public_multi_user`
2. **Public URL** *(public mode only)* — DNS, HTTPS, connection test
3. **Email & admin** *(team/public)* — SMTP, then verify admin email via OTP
4. **Integrations** *(optional)* — OAuth apps for sign-in; messaging bots
5. **Model billing** — BYOK (default) or company-pays for LLM usage
6. **Business profile** — workspace name, logo, tagline
7. **Your profile** — display name and identity
8. **Model keys** *(optional before first chat)* — connect LLM providers
9. **Native agent** — name and personality for the project concierge
10. **Invite team** *(non-public modes, optional)* — email invites
11. **Launch** — creates runtime profile, starts gateway, opens agent chat

### Invited member

1. **Your profile**
2. **Model keys**
3. **Native agent** (personal runtime binding)

After setup, sign-in uses email OTP (when SMTP is configured) or dev helpers on trusted local stacks.

## Deployment modes

| Mode | Sign-in | Typical host |
|------|---------|----------------|
| `single_user_local` | No email gate after setup | Loopback |
| `trusted_team` | Invite-only | Docker/LAN |
| `public_multi_user` | Invite-only; HTTPS required | Public VPS |

Set `WORKFRAME_DEPLOYMENT_MODE` in `.env`. The wizard may persist a choice to stack config; **`.env` wins on restart**.

Public checklist: [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md)

## After install

Each member should **Connect accounts** in the UI (LLM keys required for agent chat). Project files live under `Files/`. Agent state lives under `Agents/`.

Guides copied into generated projects (also in the installer package):

| Guide | Topic |
|-------|--------|
| [WORKFRAME_ONBOARDING.md](../../packages/create-workframe/docs/workspace-instructions/WORKFRAME_ONBOARDING.md) | Concierge onboarding loop |
| [WORKFRAME_KANBAN.md](../../packages/create-workframe/docs/workspace-instructions/WORKFRAME_KANBAN.md) | Kanban usage |
| [WORKFRAME_ROUTING.md](../../packages/create-workframe/docs/workspace-instructions/WORKFRAME_ROUTING.md) | Agent routing |
| [WORKFRAME_DOCUMENTS_AND_ARTIFACTS.md](../../packages/create-workframe/docs/workspace-instructions/WORKFRAME_DOCUMENTS_AND_ARTIFACTS.md) | Files as truth |
| [WORKFRAME_TELEGRAM.md](../../packages/create-workframe/docs/workspace-instructions/WORKFRAME_TELEGRAM.md) | Telegram |
| [WORKFRAME_DISCORD.md](../../packages/create-workframe/docs/workspace-instructions/WORKFRAME_DISCORD.md) | Discord |

## Services (default ports)

| Service | Port | Role |
|---------|------|------|
| workframe-ui | 18644 | Web UI |
| workframe-api | 19120 | API server |
| workframe-gateway | 18642 | Hermes native profile |
| workframe-dashboard | 19119 | Hermes dashboard proxy |
| workframe-supervisor | 18090 | Secure-mode exec broker |

Ports vary if you use a different `WORKFRAME_SLOT`; see `.env`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| UI **403** or blank | Static UI not built | In monorepo dev: `pnpm build:web`; generated installs ship prebuilt UI |
| Session drops on refresh | Using `localhost` | Use `http://127.0.0.1:<port>` |
| Agent chat fails | No LLM key connected | **Connect accounts** in user settings |
| Public boot refuses | HTTP or missing secrets | HTTPS `APP_BASE_URL` + [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) |

More: [Operations](./operations.md)

## Next steps

- [Using Workframe](./using-workframe.md)
- [Operations](./operations.md) — updates, backup, day-to-day
- [Security](./security.md)
- [Develop](./develop.md) — if you want to change Workframe source
