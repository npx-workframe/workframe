# WF-009 — RunAuthorityGate

## Problem

Chat, kanban, cron, slash, and webhook paths each resolve credentials independently. Payer, delegation, and deny semantics are implicit in `server.py` helpers. There is no single pre-run decision artifact tied to the domain `Run` type.

## Principle

```text
no run record without RunAuthorityGate decision
deny before lease, lease before stream
user_only providers never fall back to workspace credentials
```

## Inputs (domain + context)

| Field | Source |
|-------|--------|
| `RunSurface` | caller (chat, kanban, …) |
| `ActorType`, `actor_id` | session user or agent/webhook id |
| `triggering_user_id` | signed-in user |
| `profile_slug` | Hermes runtime profile |
| `workspace_id` | room/workspace scope |
| `provider` | billing provider id |
| `delegation_grantor_ids` | `agent_delegation_grants` for grantee |

Context probes (injected, no secrets):

| Probe | Meaning |
|-------|---------|
| `workspace_credential_mode` | `byok` or `workspace` (company-pays) |
| `provider_user_only` | dev/github/vercel — workspace creds forbidden |
| `user_has_credential` | user binding or oauth present |
| `workspace_has_credential` | workspace binding present |
| `grantor_has_credential` | map grantor_id → bool |

## Decision shape

```python
@dataclass(frozen=True)
class RunAuthorityDecision:
    allowed: bool
    deny_reason: str | None
    payer_user_id: str
    funding_source: FundingSource
    credential_ref_id: str | None
    credential_scope: str | None  # user | workspace
    grants: tuple[Grant, ...]
```

## Rules (v0.1)

### 1. Single-user BYOK (`credential_mode=byok`)

- Payer = `triggering_user_id`
- Funding = `BYOK`
- Require `user_has_credential` or oauth
- Deny: `no_credential_byok`

### 2. Company-pays (`credential_mode=workspace`)

- If user has own credential → payer user, funding `BYOK` (user key wins)
- Else if workspace credential → payer user (acting), funding `COMPANY`
- Else deny: `no_credential_company`
- `provider_user_only` → never use workspace cred; deny `provider_user_only_no_fallback`

### 3. Trusted-team delegation

- When triggering user lacks credential, check `delegation_grantor_ids` in order
- First grantor with credential becomes payer; funding `BYOK`
- Deny if none: `delegation_no_grantor_credential`

### 4. Deny reason semantics

| Reason | User-facing gist |
|--------|------------------|
| `no_actor` | missing triggering user |
| `no_credential_byok` | connect LLM under Profile |
| `no_credential_company` | admin must connect workspace LLM |
| `provider_user_only_no_fallback` | provider is personal-only |
| `delegation_no_grantor_credential` | delegator has no key |

## Outputs

On **allow**:

1. Persist `Run` (WF-NS-P2) with `status=authorized` → `running`
2. Emit `run.authorized` `RunEvent`
3. Issue `Grant` capabilities (`llm_turn` minimum)
4. Caller issues lease via `turn_credentials` (existing path)

On **deny**:

1. Persist `Run` with `status=denied`, `deny_reason`
2. Emit `run.denied` event
3. Do not issue lease or open upstream stream

## Integration points

| Surface | Hook |
|---------|------|
| Chat stream | `stream_profile_chat` — gate before `ensure_profile_api` |
| Activity | `run_events` via `run_ledger.room_activity_entries` |
| Receipt | `run_line_items` on complete (WF-016) |

## Tests

`services/workframe-api/test_run_authority.py` — pure gate matrix:

- byok + user cred → allow
- byok + no cred → deny
- workspace + workspace cred → allow company
- workspace + user cred → allow byok
- user_only + workspace only → deny
- delegation grantor with cred → allow, payer=grantor

## Dependencies

- WF-039 domain types — done
- WF-NS-P2 runs tables — same lane

## Acceptance

See `backlog.json` → `WF-009.acceptance`.
