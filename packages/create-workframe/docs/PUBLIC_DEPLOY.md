# Public multi-user deploy checklist

Use when `WORKFRAME_DEPLOYMENT_MODE=public_multi_user` — a VPS or cloud URL with **untrusted** sign-ups (e.g. `https://your.public.host`).

For trusted dogfood (1–2 operators), keep `trusted_team`. For solo local Hermes on one machine, use `single_user_local`.

## Deployment modes (login + config)

| Mode | After install completes | Boot fail-closed |
|------|-------------------------|------------------|
| `single_user_local` | No email sign-in gate | No |
| `trusted_team` | Invite-only (members + pending invitees) | No — use on loopback/LAN dogfood |
| `public_multi_user` | Invite-only (same login policy) | Yes — HTTPS `APP_BASE_URL`, vault, SMTP, proxy token, … |

**Config precedence:** `WORKFRAME_DEPLOYMENT_MODE` in `.env` wins over `stack_config.json` in runtime data. The install wizard may persist a mode to the file; restart applies the env value. Do not run `public_multi_user` on `http://127.0.0.1` — boot will refuse (HTTPS required).

**Stack config API:** `GET /api/install/stack` is public only during the install window; after that, owner/admin session required (SMTP hosts, OAuth client IDs are not anonymous).

## Before deploy

- [ ] `pnpm build:web` — `apps/web/dist` is volume-mounted; missing dist → nginx **403**
- [ ] Copy `infra/compose/workframe/.env` from `.env.example` and set **all** items in [Required `.env`](#required-env) below
- [ ] Generate secrets (never commit `.env`):
  - `bash scripts/workframe/setup-stack-secrets.sh infra/compose/workframe/.env`
  - `openssl rand -hex 32` for `ZK_AUTH_HMAC_KEY`, `ZK_AUTH_SESSION_SECRET`, `WORKFRAME_API_TOKEN`
  - `python3 -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"` for `ZK_AUTH_ENCRYPTION_KEY` (must be base64 32-byte, not hex)
- [ ] `APP_BASE_URL` = public **HTTPS** origin (no trailing path)
- [ ] SMTP provider configured (OTP + invites)
- [ ] Optional: `CORS_ALLOW_ORIGIN` and `ALLOWED_HOSTS` match your public host
- [ ] GitHub deploy key on VPS (read-only) — see `infra/vps/README.md`

## Required `.env`

```bash
WORKFRAME_DEPLOYMENT_MODE=public_multi_user
SECURE_MODE=true
# DEV_LOCAL_UNSAFE must be unset or false

WORKFRAME_SUPERVISOR_TOKEN=...   # setup-stack-secrets.sh
WORKFRAME_API_TOKEN=...
WORKFRAME_PROXY_TOKEN=...        # setup-stack-secrets.sh — gateway + API
WORKFRAME_VAULT_KEK=...          # setup-stack-secrets.sh — credential vault KEK
ZK_AUTH_HMAC_KEY=...
ZK_AUTH_ENCRYPTION_KEY=...
ZK_AUTH_SESSION_SECRET=...

SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
EMAIL_FROM=noreply@yourdomain.com
APP_BASE_URL=https://your.public.host
```

## Compose hardening (verify in repo)

- [ ] `gateway` service has **no** `env_file` (Hermes dashboard vars only; proxy token via env/volume)
- [ ] `workframe-api` + `workframe-supervisor` on `control-net`; `gateway` **not** on `control-net`
- [ ] Public overlay removes `docker.sock` from `workframe-api` (`docker-compose.public.yml`)
- [ ] `WORKFRAME_DEPLOYMENT_MODE` passed to API and supervisor containers

## Deploy

```bash
cd /opt/workframe/repo
pnpm build:web   # on build host if dist not synced
bash scripts/workframe/vps-git-pull-deploy.sh
# or: bash scripts/workframe/vps-deploy.sh from compose dir
```

**Public VPS (no API host authority):**

```bash
cd infra/compose/workframe
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build
```

**Local dogfood (admin updates from API):**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev-authority.yml up -d --build
```

## Post-deploy verification

```bash
cd /opt/workframe/repo
bash scripts/workframe/verify-public-deploy.sh
```

Manual smoke:

| Check | Expected |
|-------|----------|
| `GET /api/health` | `deployment_mode: public_multi_user`, `mode: secure`, `proxy_token_configured: true`, `vault_envelope: true`, `docker_sock_on_api: false` |
| `GET /hermes-dashboard/` (no cookie) | **403** |
| Member UI | No Dashboard nav link |
| Owner/admin UI | Dashboard opens |
| `docker inspect workframe-gateway` env | No `ZK_AUTH_*`, `WORKFRAME_SUPERVISOR_TOKEN`, `SMTP_PASS` |
| Gateway → supervisor network | Gateway cannot resolve `workframe-supervisor` |

## Security behavior (public mode)

| Control | Behavior |
|---------|----------|
| Auth | Session required; invite-only for all multi-user modes post-install (no open OTP signup) |
| Dashboard | nginx `auth_request`; owner/admin only |
| Gateway env | Allowlist only |
| Supervisor exec | Blocks shell paths to `profiles/u-*/.env` and `auth.json` |
| Runtime profile RBAC | Members may only exec/chat on their own `u-{user}-*` profiles (public); owners may delegate in trusted_team |
| Internal LLM proxy | Lease token + `X-Workframe-Proxy-Token` from gateway env (not on shared profile mount) |
| Credential vault | Envelope v2 (per-secret DEK + KEK); vault DB not mounted on gateway |
| Agent toolsets | **Full** (`hermes-cli` + `terminal`) on `/workspace` — credential isolation via vault + proxy token, not disabled shell |
| Kanban delegation | Assignee **owner** pays (not initiator) |

## Known ceiling

Hermes still mounts the full `runtime/Agents` tree in the gateway container. Multi-user safety relies on **runtime profile RBAC**, **supervisor/BFF exec blocks** on `profiles/u-*/.env` and `auth.json`, and **per-user runtime profiles** for BYOK — not on removing terminal. A future step is per-user mount namespaces or Hermes credential channels for defense in depth.

## Rollback

```bash
cd infra/compose/workframe
docker compose down
# restore prior .env + runtime backup, then:
docker compose up -d --build
```

Rotate `WORKFRAME_SUPERVISOR_TOKEN`, `WORKFRAME_API_TOKEN`, and `ZK_AUTH_*` if compromise is suspected.
