# Loop engineering — Workframe in the portfolio

Workframe uses the same **loop engineering** pattern as living-knowledge, autocorp, mktintel, and TKG: durable ledgers, one role per run, queues over ad-hoc prompts.

## Industry crash course (2026)

The AI agent stack has converged on two disciplines:

| Discipline | Owns | Failure if neglected |
|------------|------|----------------------|
| **Loop engineering** | Perceive → reason → act → observe; exit conditions; verification | Runs forever, stops early, or “done” without proof |
| **Harness engineering** | Sandboxes, tools, memory, permissions, hooks, observability | Breaks in production; invisible failures |

**Convergence signals:** ReAct-style tool loops everywhere (Cursor, Codex, Claude Code, Copilot); MCP tool surfaces; worktree isolation; planner/worker/judge splits; **Harness-as-a-Service** (you configure the runtime, not the loop from scratch).

**Implication for Workframe:** Hermes is a **replaceable engine adapter**. Workframe’s product is the **business harness** — cells, runs, brokers, audit — around whatever loop the engine runs.

References: [Addy Osmani's harness engineering](https://addyosmani.com/blog/agent-harness-engineering/), [MindStudio loop vs harness](https://www.mindstudio.ai/blog/loop-engineering-vs-harness-engineering), [pipeline convergence](https://codex.danielvaughan.com/2026/04/15/coding-agent-pipeline-convergence/).

## Architectonic pattern (your stack)

```text
Observe → Plan → Act → Evaluate → Repair/Learn → Persist → Repeat
```

```text
single coordinator (scheduler)
many roles
shared daily ledger (operations/daily/YYYY-MM-DD/)
queues.json + status.json
one role per run, then stop
```

**living-knowledge** (`architectonic-living-knowledge`) defines the reusable contract: campaigns, verification gates, cartographer/enricher/critic roles, repair-before-growth priority.

**Portfolio schedulers** (see Architectonic ABKB `operations/registry/scheduler-ownership.md`):

| Runtime | Repos | Ledger path |
|---------|-------|-------------|
| **ChatGPT** | autocorp, mktintel, TKG, skills | Each repo `operations/daily/` or `meta/daily/` |
| **Cursor** | ABKB, **workframe** | ABKB `operations/daily/`; Workframe `.harness/` + `docs/ledger/` |

ChatGPT **supervisor** writes portfolio digest; Cursor **meta operator** runs Drift Scout / Reporter without re-auditing app repos unless SHA drift.

## Workframe’s loops

| Loop | Location | Purpose |
|------|----------|---------|
| **Product verify** | `.harness/feature_list.json`, `verify.mjs` | Scenario pass/fail — closest to “verification” in loop engineering |
| **Public ledger** | `docs/ledger/` | Human-readable now / audits / north-star status |
| **Operator log** | `operations/log.md` | Session handoff |
| **Release** | `workframe-release` skill | Source → installer parity → pack → install-gate |

Workframe does **not** yet run a daily `operations/daily/` folder in-repo; the harness + ledger fill that role for Cursor-owned product work. App repos (autocorp, mktintel, TKG) use ChatGPT daily ledgers for corpus/campaign maintenance.

## Cursor’s role

Cursor is the **implementation harness** for Workframe and ABKB meta upkeep: edit canonical source, run verify, open PRs, update ledger rows. It is not the portfolio CEO (that remains ChatGPT supervisor for venture repos until CEO persona is fully stubbed).

**Alignment:** North-star “run ledger” and “credential broker” are harness primitives; v0.1.x proves installer + vault + proxy while loop-engineering discipline keeps planning from becoming a transcript dump — link evidence, one status file, repair before growth.
