# Glossary

Canonical Workframe vocabulary (WF-NS-P0). Entity shapes live in `services/workframe-api/domain/` (WF-039). Prefer these terms over Hermes-profile-as-catch-all.

## Deployment and tenancy

| Term | Definition |
|------|------------|
| **Cell** | One Workframe install — generated project root with manifest, compose, `Agents/`, and `Files/`. Authority boundary for open, update, connect, and adopt. |
| **Workspace** | Logical team/project inside a cell (`workspace_id`, slug). Holds rooms, members, and agent registry. |
| **User** | Authenticated member with role (`owner`, `admin`, `member`, `guest`) in a workspace. |
| **Room** | Collaboration channel (space or DM) scoped to a workspace. Not a domain entity in WF-039; referenced by `Run.room_id`. |

## Agents and runtimes

| Term | Definition |
|------|------------|
| **AgentIdentity** | Persistent Workframe agent — template, display name, native flag. Distinct from any Hermes profile (WF-013 seam). |
| **RuntimeBinding** | Link from `AgentIdentity` to a concrete runtime (`runtime_kind`, `profile_slug`, status). Hermes managed Docker is the v0.1.x executable binding. |
| **Lane** | UI tab/route to an agent — presentation; binding resolves to `AgentIdentity` + `RuntimeBinding`. |
| **Hermes profile** | Hermes runtime home (`Agents/profiles/...`). Implementation detail behind `RuntimeBinding`, not a substitute for agent identity. |

## Authority and execution

| Term | Definition |
|------|------------|
| **Run** | Unit of authority, execution, and economics. Created by chat, @mention, kanban, cron, slash, or webhook. Carries actor, surface, payer, and status. |
| **RunEvent** | Append-only ledger entry for a run (`event_type`, `payload`). Feeds Activity and audit. |
| **Grant** | Capability allowed for a run (`llm_turn`, `file_write`, `broker_egress`, …) after policy gates. |
| **Surface** | Product panel or entry point that may create or display runs (`chat`, `files`, `agent_rail`, …). See [WF-010 surface contracts](../ledger/specs/WF-010/spec.md). |

## Credentials and funding

| Term | Definition |
|------|------------|
| **CredentialRef** | Vault pointer to a provider secret — never raw key material in API or UI. |
| **Lease** | Short-lived scoped token (`wf_rt_*`) tying a run to a `CredentialRef` and payer. Gateway uses lease; API holds secrets. |
| **BYOK** | Bring-your-own-key — user connects providers; `FundingSource.byok`. |
| **Company-pays** | Stack-managed keys on native profile; `FundingSource.company`. |
| **user_only** | Provider policy — no workspace credential fallback (`CredentialPolicy.user_only`). |

## Gates (design / implementation)

| Term | Definition |
|------|------------|
| **CellAuthorityGate** | Decides whether a cell may be created, opened read-only, updated, connected remotely, or adopt a runtime. Design: [WF-007](../ledger/specs/WF-007/spec.md). |
| **RunAuthorityGate** | Single pre-run decision: actor, agent, runtime, provider, credential, payer, delegation, deny reason. WF-009 (not yet implemented). |
| **SurfaceContractGate** | Per-surface contract: reads, writes, authority gate, evidence. [WF-010](../ledger/specs/WF-010/spec.md). |

## Truth model

```text
Files  >  Kanban  >  Chat
```

**Files** hold durable project truth. **Kanban** tracks execution. **Chat** coordinates intent.

## Related docs

- [Architecture](./architecture.md)
- [Session architecture](./session-architecture.md)
- [Security](./security.md)
- Domain JSON schema: `services/workframe-api/domain/schema/workframe-domain.schema.json`
