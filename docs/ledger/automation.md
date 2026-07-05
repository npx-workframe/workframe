# Ledger automation protocol

How autonomous agents use [`backlog.json`](backlog.json) as the single work queue.

## Loop (implementer ↔ reviewer)

```text
1. Agent wakes → read backlog.json + backlog.md + now.md
2. Pick next item (ledger-next.mjs) OR human-assigned id
3. Claim: status=in_progress, workflow.assignee, workflow.claimed_at
4. If item lacks spec and wave=release-truth|authority|broker:
     create docs/ledger/specs/<ID>/spec.md (spec-kit shape)
5. Implement patch → link workflow.patch_refs (commit SHAs)
6. Set status=review, workflow.reviewer role queued
7. Reviewer agent: read patch_refs, run harness, set done|todo (with notes)
8. Update evidence[] and now.md if shipping surface changed
9. Commit backlog.json with the code patch (same PR)
```

**One role per run** (Architectonic rule): implementer *or* reviewer *or* ledger clerk — not all three in one unattended turn without explicit override.

## Status transitions

| From | To | Who | Requirement |
|------|-----|-----|-------------|
| todo | in_progress | implementer | `depends_on` items done or waived in notes |
| in_progress | review | implementer | `patch_refs` non-empty |
| review | done | reviewer | acceptance met + harness/evidence |
| review | todo | reviewer | FAIL notes in `workflow.notes` |
| * | blocked | any | External dependency documented |
| deferred | todo | human | Explicit re-prioritization |

## Priority pick order

1. `P0` + `status=todo` + no unmet `depends_on`
2. `review` items (clear the queue)
3. `P1` in active wave (release-truth → authority → broker)
4. Never start `deferred` without human or CEO ledger edit

## Files agents may mutate

| File | Role |
|------|------|
| `docs/ledger/backlog.json` | Status, workflow, evidence |
| `docs/ledger/now.md` | Shipping summary when item done |
| `docs/ledger/specs/<ID>/*` | Spec-kit artifacts per item |
| `operations/log.md` | Session handoff narrative |

Do **not** use the ledger to replace git history or `.harness/feature_list.json` — link them in `evidence`.

## Harness binding

Map completed items to harness scenarios when applicable:

| Backlog | Harness scenario |
|---------|------------------|
| WF-002, WF-021 | `dogfood-install-gate` |
| WF-012 | `installer-ui-bundle` |
| WF-022, WF-001 | new `version-agreement` (to add) |
| WF-028 | API self-check / new lease tests |

## Daily ledger (portfolio)

ABKB `operations/daily/` tracks **meta** upkeep. Workframe product work lives in **`docs/ledger/backlog.json`**. Reporter role can copy a digest into ABKB supervisor output — do not fork two competing queues.

## CLI

```bash
# Next implementer item
node scripts/workframe/ledger-next.mjs

# Next item needing review
node scripts/workframe/ledger-next.mjs --role reviewer

# Specific item
node scripts/workframe/ledger-next.mjs --id WF-002

# JSON only (for schedulers)
node scripts/workframe/ledger-next.mjs --json
```

## Future automation

- GitHub Action: `ledger-next` → opens agent job with item payload
- Workframe kanban card ↔ `WF-*` id
- ChatGPT supervisor reads `backlog.json` summary for portfolio standup
- Spec-kit `/speckit.implement` bound to `docs/ledger/specs/<ID>/tasks.md`
