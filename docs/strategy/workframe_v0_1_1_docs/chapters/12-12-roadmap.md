# Roadmap from Current Workframe

The roadmap should avoid a rewrite. Preserve the current product, but move authority into Workframe-owned primitives.

## Phase 0 - Vocabulary lock

Define and use these terms consistently:

```text
Cell
Workspace
Room
Board
Card
Actor
AgentProfile
Run
Runtime
Engine
Capability
Lease
Artifact
AuditEvent
BillingEvent
```

Stop using Hermes profile as a catch-all for agent, runtime, session, authority, and memory.

## Phase 1 - Harden current stack

Immediate work:

```text
remove Docker socket from workframe-api
keep socket only in supervisor
put arbitrary exec behind dev-unsafe only
route all model usage through LLM proxy and wf_rt leases
stop writing raw model keys into profile .env for turns
store provider metadata separately from secrets
add tests proving API cannot access Docker socket
```

## Phase 2 - Add Workframe-owned runs

Add minimum tables:

```sql
runs(
  id,
  workspace_id,
  room_id,
  card_id,
  actor_type,
  actor_id,
  triggering_user_id,
  engine,
  runtime,
  status,
  risk_tier,
  budget_usd,
  created_at,
  started_at,
  ended_at
)
```

```sql
run_events(
  id,
  run_id,
  event_type,
  payload_json,
  created_at
)
```

```sql
run_line_items(
  id,
  run_id,
  funding_source,
  vendor,
  meter,
  quantity,
  unit_cost,
  total_cost,
  created_at
)
```

Then make these create runs:

```text
agent DM
space @mention
card assignment
cron job
manual slash command
external webhook
```

## Phase 3 - Tool and credential brokers

Generalize the existing LLM proxy pattern:

```text
LLM proxy -> model broker
GitHub actions -> git broker
Slack/Discord/TG -> message broker
Vercel/Netlify -> deploy broker
Google Workspace -> document/mail/calendar broker
MCP -> capability-filtered tool broker
```

## Phase 4 - Runtime/engine adapter seam

Introduce two interfaces:

```text
EngineAdapter:
  Hermes
  Pi
  Claude Code
  Codex
  OpenCode
  AG2-style orchestrator

RuntimeAdapter:
  Hermes profile runtime
  AgentOS lightweight VM
  local daemon
  full sandbox
  BYOC runner
  Kubernetes job
```

This makes future runtimes additive instead of disruptive.

**Implementation status (2026-06-26):** Design only. Near-term delivery split into two steps in `docs/workframe/`:

| Step | Scope | Doc |
|------|-------|-----|
| 1 | `runtime_kind`, host resolver, NemoHermes stub, Stripe broker, supervisor guard | `adapter-step1-runtime-seam.md` |
| 2 | `EngineAdapter` / `RuntimeAdapter` Protocol extract; Hermes as first implementation | `adapter-step2-engine-extract.md` |

Build checklist: `adapter-build-roadmap.md`. Upstream refs (Hermes, NemoClaw): `adapter-external-references.md`.

## Phase 5 - File manifests and artifacts

Move from broad workspace mounts to run-scoped file manifests.

Early implementation:

```text
copy allowed files into run workspace
agent writes artifacts
human or policy promotes artifacts back
ledger records file diff
```

Later implementation:

```text
overlay filesystem
object storage backend
git branch mount
AgentOS virtual filesystem
sandbox bind mounts
```

## Phase 6 - Workframe Cell productization

Add cell metadata:

```text
cell_id
deployment_mode
owner_workspace
version
health
update_channel
runtime_capacity
backup_config
secret_mode
egress_mode
installed_adapters
license_state
```

Build tooling for:

```text
install
upgrade
backup
restore
health check
domain setup
email allowlist
provider connect
usage export
support bundle
```

## Phase 7 - Provisioned/BYOC control plane

Build the cloud-side manager for:

```text
provisioning VPS/cloud cells
tracking cell versions
pushing updates
licensing
billing
usage credits
template installation
marketplace access
support diagnostics
```

## Phase 8 - Marketplace and payment rails

Only after runs, capabilities, and billing are stable:

```text
agent marketplace
skill marketplace
playbook marketplace
runtime marketplace
connector marketplace
agent-to-agent payments
x402/crypto experiments
```
