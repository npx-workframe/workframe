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

## Agent egress and the credential broker

Hermes agents need the open internet — web research, docs, public APIs, and normal tool use must stay fast and unrestricted. Security work is **not** about blocking that traffic.

Workframe splits outbound traffic into two classes:

| Class | Examples | Policy |
|-------|----------|--------|
| **General egress** | Web search, `fetch`, public HTTPS, package indexes | **Allowed** — direct from the gateway container; no broker hop, no per-action approval |
| **Brokered egress** | LLM providers, GitHub/Vercel/Netlify when using vault credentials | **Required** — `wf_rt_*` lease + internal proxy; raw secrets stay in the API vault |

```text
Hermes (gateway)
  ├─ general egress ──────────► internet (research, tools, public APIs)
  └─ brokered egress ─────────► workframe-api (/internal/llm/*, /internal/action/*)
                                    └─ vault + lease validation ─► upstream provider
```

### What “unavoidable broker” means

In `public_multi_user`, credential-mediated traffic must not depend on agent cooperation alone. Concretely:

1. Gateway must **not** receive raw provider API keys or the vault database.
2. Runtime profiles use **lease tokens** (`wf_rt_*`) and internal proxy base URLs for LLM calls.
3. Integrated action providers use `/internal/action/*` with the same lease model.
4. Gateway must **not** join the supervisor `control-net` (already enforced in compose).
5. Optional strict profile (`WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true`) blocks **direct** outbound connections to known provider API hostnames via the `gateway-egress-guard` iptables sidecar (`docker-compose.egress-broker.yml`) so traffic must use the broker — general internet stays open.

This is **routing and secret placement**, not disabling `terminal` or adding human approval before each tool call. Lease validation on brokered requests is in-process (milliseconds), not an operator gate.

### Deployment posture

| Mode | General egress | Brokered credentials |
|------|----------------|----------------------|
| `trusted_team` / dogfood | Unrestricted | Config + vault + leases (today) |
| `public_multi_user` | Unrestricted (agents stay capable) | Same broker path; verify script reports posture |
| `public_multi_user` + `WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true` | Unrestricted except provider-host deny via egress-guard sidecar | Network-enforced broker path |

See also [Audit 0027 — Agent Vault comparison](../audits/0027-agent-vault-comparison.md) (advisory; Infisical Agent Vault as a reference pattern, not a required dependency).

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
