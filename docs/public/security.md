# Security

Report vulnerabilities via [SECURITY.md](../../SECURITY.md) — not public GitHub issues.

## Modes

| Variable | Effect |
|----------|--------|
| `SECURE_MODE=true` | Auth on mutating routes, restricted CORS, no Docker socket on API |
| `DEV_LOCAL_UNSAFE=true` | Development only — open CORS, relaxed auth |
| *(neither set)* | Secure default |

Never enable `DEV_LOCAL_UNSAFE` or `WORKFRAME_E2E=1` on a public HTTPS URL during the install window.

## Supervisor boundary

With `SECURE_MODE=true`:

- Only `workframe-supervisor` mounts `/var/run/docker.sock`
- API calls supervisor with `WORKFRAME_SUPERVISOR_TOKEN`
- Public compose overlay removes the socket from `workframe-api`

## Credentials

- **BYOK default** — user keys in per-user Hermes homes
- **`user_only` providers** — no workspace fallback
- **Vault** — envelope encryption; not mounted on the gateway container
- **Per-turn leases** — gateway proxy tokens instead of shared raw secrets

## Public multi-user (`public_multi_user`)

| Control | Behavior |
|---------|----------|
| Boot | Requires HTTPS, vault KEK, SMTP, proxy token, supervisor token |
| Auth | Invite-only after install |
| Dashboard | Owner/admin only (`auth_request`) |
| Runtime RBAC | Members limited to their own `u-{user}-*` profiles |
| Gateway env | Allowlisted secrets only |
| Supervisor | Blocks direct access to user `.env` and `auth.json` paths |

Full checklist: [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md).

## Multi-user filesystem model

The Hermes gateway container mounts the shared `Agents/` tree. User isolation uses per-user runtime profiles, role checks in the API, supervisor guards, and encrypted credentials. Read [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) before running a public multi-user install.
