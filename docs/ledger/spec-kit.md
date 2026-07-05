# Spec-kit integration

[GitHub spec-kit](https://github.com/github/spec-kit) — **Spec-Driven Development**: constitution → specify → plan → tasks → implement, with agent slash commands (`/speckit.*`).

## Fit with Workframe ledger

We already have parallel artifacts. **Do not duplicate** — map layers:

| Spec-kit | Workframe equivalent | Location |
|----------|---------------------|----------|
| **constitution** | Product doctrine + agent rules | `AGENTS.md`, [north-star.md](north-star.md), [security.md](../public/security.md) |
| **specify** (`spec.md`) | What/why for one backlog item | `docs/ledger/specs/<WF-ID>/spec.md` |
| **plan** (`plan.md`) | How/tech constraints | `docs/ledger/specs/<WF-ID>/plan.md` |
| **tasks** (`tasks.md`) | Checklist derived from acceptance[] | `docs/ledger/specs/<WF-ID>/tasks.md` or `backlog.json` acceptance |
| **implement** | Code patch + harness | git + `.harness/verify.mjs` |
| **(missing in spec-kit)** | **review gate** | `backlog.json` status `review` → `done` |

**Single queue:** [`backlog.json`](backlog.json). Spec-kit folders are **per-item depth**, not a second backlog.

## Adoption options

| Option | Pros | Cons |
|--------|------|------|
| **A. Map only (now)** | No new deps; Cursor uses ledger protocol | No `/speckit.*` commands until templates installed |
| **B. `specify init` in repo** | Native slash commands for Cursor/Copilot | Adds `.specify/` + template churn; merge with existing AGENTS.md |
| **C. Git submodule `vendor/spec-kit`** | Pin templates/commands; offline read | Submodule maintenance; 118k-star repo size |
| **D. Architectonic layer package** | Publish `architectonic-spec` wrapping spec-kit + ledger schema for all org repos | Upfront packaging work |

**Recommendation:** **A → B** for Workframe. Run `specify init` with `--integration cursor` after backlog stabilizes; point constitution at existing `AGENTS.md` + north-star doctrine instead of generating a competing one.

```bash
# When ready (requires uv + specify-cli)
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
cd d:/ab/projects/workframe
specify init . --here --integration cursor --force
# Then merge .specify/ templates with docs/ledger/specs/ paths in automation.md
```

Do **not** clone spec-kit into `vendor/` until we pin a release tag and add submodule policy to ABKB registry.

## Relation to living-knowledge / ABKB loops

| System | Queue | Spec shape |
|--------|-------|------------|
| living-knowledge | `operations/daily/queues.json` | campaigns + corpus items |
| ABKB meta | `operations/daily/queues.json` | profile refresh, drift |
| Workframe | `docs/ledger/backlog.json` | WF-* items + spec-kit specs/ |
| spec-kit (generic) | `tasks.md` per feature | product feature specs |

**Convergence:** Architectonic `living-knowledge` loop-engineering doc is the **meta-pattern**; spec-kit is the **product-dev command surface**; Workframe ledger is the **Workframe program backlog**.

## Backlog item WF-SK-001

Track spec-kit adoption in [`backlog.json`](backlog.json) (`WF-SK-001`). Done when:

- This mapping is stable (done)
- First P0 item has `docs/ledger/specs/WF-002/` spec+plan+tasks
- Optional: `specify init` merged without duplicating constitution

## Industry context

Spec-kit is the **spec/harness** side of 2026 agent engineering; our ledger is the **program management** side. Together they match:

- **Loop engineering** — iteration until acceptance[] met
- **Harness engineering** — AGENTS.md, harness, supervisor, brokers
- **Spec-driven development** — executable specs before code

See [loops.md](loops.md).
