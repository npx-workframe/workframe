# Security audit guide

For evaluators reviewing Workframe before install or public deployment. Read in this order, then run verification scripts against your stack.

## 1. Threat model (plain language)

| Asset | Risk if compromised |
|-------|---------------------|
| **User LLM/integration keys** | Unauthorized API spend, repo/deploy access |
| **`Agents/` tree** | Agent impersonation, credential theft |
| **`Files/` workspace** | Project data leak or destruction |
| **Session cookies / zk-auth keys** | Account takeover |
| **Docker socket** | Container escape → host RCE |

Workframe mitigates with: encrypted vault, per-user runtime profiles, supervisor-only Docker access, gateway env allowlists, RBAC on runtime profiles, and invite-only multi-user auth.

## 2. Documentation

| Doc | Focus |
|-----|--------|
| [Security](./security.md) | Modes, vault, supervisor boundary |
| [Architecture](./architecture.md) | Components and data flow |
| [Session architecture](./session-architecture.md) | Chat binding and isolation |
| [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) | Public VPS hardening checklist |
| [schema.sql](./schema.sql) | Persisted state |
| [SECURITY.md](../../SECURITY.md) | Vulnerability reporting |

## 3. Source code (monorepo)

Read these paths for behavior that matters to trust:

| Path | Why |
|------|-----|
| `services/workframe-api/server.py` | Auth gates, install window, vault, rooms, Hermes proxy, RBAC |
| `services/workframe-api/zk_auth.py` | Session and credential crypto (via zk-auth) |
| `services/workframe-supervisor/server.py` | Docker exec broker; path blocks on user secrets |
| `apps/web/src/components/onboarding/` | Install wizard; what gets configured when |
| `infra/compose/workframe/docker-compose.yml` | Service topology, mounts, networks |
| `infra/compose/workframe/docker-compose.public.yml` | Public overlay (no API docker.sock) |
| `infra/compose/workframe/.env.example` | Required secrets and modes |

Generated installs ship copies of API/supervisor/UI from the npm package — verify version integrity via [VERSION.md](../VERSION.md) and npm pack contents if auditing a deployed project.

## 4. Key security behaviors to verify

### Install window

Sensitive `/api/install/*` routes are only open before setup completes. After install, stack config and SMTP details require owner/admin session.

### Credential isolation

- BYOK default; `user_only` providers (GitHub, Vercel, Netlify) do not fall back to workspace keys
- Vault encrypted at rest; gateway uses short-lived lease tokens
- Supervisor blocks exec paths targeting `profiles/u-*/.env` and `auth.json`

### Multi-user profiles

Members may only chat/exec on their own `u-{user}-*` runtime profiles. Owners/admins have broader access per deployment mode.

### Public mode boot

`public_multi_user` fails closed without HTTPS, SMTP, vault KEK, proxy token, and auth secrets.

## 5. Automated verification

From repository root (or on VPS with repo checkout):

```bash
bash scripts/workframe/verify-public-deploy.sh
```

For `public_multi_user`, this checks env vars, compose overlays, and container posture. With other modes it exits early after confirming mode.

Manual smoke (public deploy):

| Check | Expected |
|-------|----------|
| `GET /api/health` | `mode: secure`, `docker_sock_on_api: false`, vault/proxy configured |
| `GET /hermes-dashboard/` without session | **403** for non-admin |
| Gateway container env | No raw `SMTP_PASS`, `ZK_AUTH_*`, supervisor token |

Full table: [PUBLIC_DEPLOY.md § Post-deploy verification](../../infra/compose/workframe/PUBLIC_DEPLOY.md#post-deploy-verification)

## 6. What is out of scope

- Personal Hermes installs outside a Workframe compose stack (unless the bug is in shared Workframe source)
- Host OS hardening beyond what compose documents
- Third-party LLM provider security

Report issues via [SECURITY.md](../../SECURITY.md) — not public GitHub issues for sensitive findings.

## 7. Decision checklist

Before trusting a **public** install:

- [ ] Read [Security](./security.md) and [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md)
- [ ] `WORKFRAME_DEPLOYMENT_MODE=public_multi_user`, `SECURE_MODE=true`, `DEV_LOCAL_UNSAFE` off
- [ ] Ran `verify-public-deploy.sh` green
- [ ] Confirmed gateway env allowlist and dashboard auth
- [ ] Understood shared `Agents/` mount model in [Architecture § Multi-user](./architecture.md)

Before trusting a **local team** install:

- [ ] Invite-only auth configured
- [ ] Each user connects own LLM keys (unless company-pays is intentional)
- [ ] Backups planned for `Agents/`, `Files/`, and API data — see [Operations](./operations.md)
