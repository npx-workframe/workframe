# Workframe ledger

Single public index for **what we ship now**, **where we are going**, and **what audits found**. Source code remains truth; this ledger links artifacts and records status.

## Read order

| I want to… | Start here |
|------------|------------|
| **Know current priorities** | [now.md](now.md) |
| **Understand long-term vision** | [north-star.md](north-star.md) → [strategy brief](../strategy/workframe_v0_1_1_docs/WORKFRAME_v0.1.1_MASTER.md) |
| **Trace an audit finding** | [audits.md](audits.md) |
| **Pick up work (agents)** | [backlog.json](backlog.json) · [automation.md](automation.md) |
| **See how autonomous loops run** | [loops.md](loops.md) |
| **Install / operate / secure** | [public docs index](../README.md) |

## Layers (do not merge)

```text
docs/public/           Ship-facing product docs (users, evaluators, contributors)
docs/ledger/           Status spine — now, backlog.json, audit registry, loop model
docs/strategy/         Full north-star brief (v0.1.1 strategy package)
archive/planning/living-audit/     Planning archive — convergence work toward the cell product
docs/audits/           Numbered point-in-time security/architecture audits
.harness/              Executable verification loop (feature scenarios + verify.mjs)
operations/log.md      Operator session log (repo root)
```

**Authority rule:** Implementation truth = source + harness green. Ledger rows are planning/status unless linked evidence is a passing gate or merged code path.

## Status vocabulary

| Status | Meaning |
|--------|---------|
| **shipped** | In `main`, user-visible or operator-verified |
| **partial** | Primitive exists; product surface or enforcement incomplete |
| **planned** | Documented target; no runtime enforcement yet |
| **deferred** | North-star scope; not this wedge |
| **superseded** | Kept for history; see newer row |

## Loop engineering (portfolio)

Workframe participates in the Architectonic **loop-engineering** model: one scheduler, one role per run, durable ledger on disk. See [loops.md](loops.md) for how this repo connects to living-knowledge, autocorp, mktintel, TKG, and Cursor.

## Maintenance

When you close an audit item, add a release note, or change north-star scope:

1. Update the row in [audits.md](audits.md) or [now.md](now.md).
2. Link evidence (commit, harness scenario, or doc path).
3. Do not duplicate prose — link the source artifact.
