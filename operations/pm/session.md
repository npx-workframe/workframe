# PM session boot

Run this at the start of **every** Workframe chat or automation.

## 1. Orient (10 s)

```powershell
cd <workframe-repo>
git status -sb
git log main -3 --oneline
```

## 2. Read ledgers (30 s)

| Order | File |
|-------|------|
| 1 | [docs/ledger/now.md](../../docs/ledger/now.md) |
| 2 | [docs/ledger/backlog.json](../../docs/ledger/backlog.json) — filter `status: todo|in_progress|review` |
| 3 | [.harness/feature_list.json](../../.harness/feature_list.json) — `passes: false` |
| 4 | [operations/pm/queues.json](queues.json) |
| 5 | Alan's message (overrides queue) |

## 3. Pick mode

| Mode | When | Next |
|------|------|------|
| **PM** | Plan, prioritize, enqueue | Update backlog + queues; no code |
| **Execute** | Alan gave a task or `ledger-next` | [runbook.md](runbook.md) → patch |
| **Review** | `status: review` items | Harness + merge guidance |

```powershell
node scripts/workframe/ledger-next.mjs
node scripts/workframe/ledger-next.mjs --role reviewer
```

## 4. Source cascade (before any edit)

```text
START_HERE.md → AGENTS.md → grep/read target file → smallest patch
```

ABKB: `projects/workframe/agent-rail.md` for pitfalls only.

## 5. Close session

Append one line to [operations/log.md](../log.md):

```text
ISO | pm-workframe | <outcome> — WF-xxx if applicable
```

Update `backlog.json` workflow fields if item moved.

## Dogfood quick ref

| Action | Command |
|--------|---------|
| Local install | `../MyBusiness` — slot 1 `18644` |
| Wipe sandbox | `.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm` |
| Sign-off | `.\scripts\workframe\sign-off-install.ps1` |
| Routine update | Browser Admin → Updates → Workframe |
| URL | `http://127.0.0.1:18644` (not localhost) |

Full detail: [runbook.md](runbook.md).
