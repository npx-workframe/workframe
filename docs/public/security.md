# Security

Reporting vulnerabilities: see [SECURITY.md](../../SECURITY.md).

Implementation: `services/workframe-api/server.py`, `services/workframe-supervisor/server.py`, `infra/compose/workframe/docker-compose*.yml`.

## Security modes

| Variable | Effect |
|----------|--------|
| `SECURE_MODE=true` | Production posture: auth on mutating routes, CORS restricted, no Docker socket on API |
| `DEV_LOCAL_UNSAFE=true` | Development only: open CORS, relaxed auth, API may use Docker socket directly |
| *(neither set)* | **Secure default** |

These flags are mutually exclusive. Startup refuses if both are set.

**Never** enable `DEV_LOCAL_UNSAFE` or `WORKFRAME_E2E=1` on a public HTTPS URL during the install window — they expose first-admin takeover risk via OTP-in-JSON or CSRF chains.

## workframe-supervisor

When `SECURE_MODE=true`:

- Only the supervisor container mounts `/var/run/docker.sock`
- BFF calls supervisor over HTTP with `WORKFRAME_SUPERVISOR_TOKEN`
- Gateway lifecycle and Hermes exec go through `/v1/gateway.exec` and `/v1/hermes.user_exec`

Public compose overlay (`docker-compose.public.yml`) removes the Docker socket from `workframe-api`.

## Credential policy

- **BYOK default** — users connect their own LLM and integration keys
- **`user_only` providers** — no workspace credential fallback
- **Vault** — envelope encryption with `WORKFRAME_VAULT_KEK`; vault DB not mounted on gateway
- **Per-turn leases** — gateway uses short-lived proxy tokens, not raw user secrets on shared profile mounts

## Public multi-user controls

When `WORKFRAME_DEPLOYMENT_MODE=public_multi_user`:

| Control | Behavior |
|---------|----------|
| Boot | Fail-closed without HTTPS `APP_BASE_URL`, vault KEK, SMTP, proxy token, supervisor token |
| Auth | Invite-only after install; no anonymous stack config reads |
| Dashboard | nginx `auth_request`; owner/admin only |
| Runtime RBAC | Members exec/chat only on their own `u-{user}-*` profiles |
| Gateway env | Allowlist only — no SMTP auth secrets in gateway container |
| Supervisor | Blocks shell paths to `profiles/u-*/.env` and `auth.json` |

Full checklist: [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md).

## Known ceiling

Hermes mounts the full `Agents/` tree in the gateway container. Multi-user safety relies on runtime profile RBAC, supervisor exec blocks, per-user runtime profiles, and vault/proxy tokens — not on removing shell access to `/workspace`. Defense-in-depth (per-user mount namespaces) is a future hardening step.

## Install-window test flags

| Flag | Purpose | Safe when |
|------|---------|-----------|
| `WORKFRAME_E2E=1` | OTP in JSON for Playwright | Loopback only, install window only |
| `WORKFRAME_E2E_UNSAFE=1` | Gate for slot-3 specs needing dev-unsafe stack | CI/local only |
| `DEV_LOCAL_UNSAFE=true` | Skip auth for local dogfood | Trusted local operators only |

After `install_complete`, OTP JSON exposure stops for E2E mode.
