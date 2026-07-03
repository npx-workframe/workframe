# Workframe harness ledger

**Product operator ledger** for Cursor-owned Workframe loops.

## Files

| File | Role |
|------|------|
| `feature_list.json` | Canonical scenario list: `id`, `verify` command, `passes`, `owner` |
| `verify.mjs` | Runs `owner: cursor-cloud` scenarios; writes `passes` |
| `progress.txt` | Human notes (non-machine) |

## Owners

| Owner | Where it runs |
|-------|----------------|
| `cursor-cloud` | CI + Cursor cloud agent (`pnpm test:ci`, `.cursor/environment.json`) |
| `cursor-local` | Your machine (install-gate, UI bundle parity) |

## CI

`.github/workflows/ci.yml` sets `HARNESS_CHECK=1` and runs `node .harness/verify.mjs`.

## Assignment rail (cross-repo)

PMs enqueue tasks in ABKB:

`d:/ab/projects/abkb/operations/daily/YYYY-MM-DD/queues.json` → `work_items`

Workers complete a `work_items` entry **and** update harness `passes` when acceptance requires it.

## Adding a scenario

1. Add entry to `feature_list.json` with smallest `verify` command.
2. Run `node .harness/verify.mjs --check` locally.
3. PR with `passes: false` until green (ponytail: one scenario per PR when possible).
