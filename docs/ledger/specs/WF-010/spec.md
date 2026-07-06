# WF-010 — SurfaceContractGate

## Problem

The five-panel UI spine (agent rail, chat, files, browser, activity) compresses several authority, security, and evidence boundaries. Public docs and panel labels can over-sell capabilities before gates and receipts exist.

## Outcome

A committed contract table per surface: what it reads, what it writes, which authority gate applies, and how harness or manual evidence proves the contract.

## v0.1.x product spine

Only these five dock panels are release-blocking product surfaces. Other capabilities (Kanban, skills, slash, team admin) are Hermes-backed or mode-gated extensions.

## Surface contract table

| Surface | Reads | Writes | Authority gate | Evidence path |
|---------|-------|--------|----------------|---------------|
| **Agent rail** | Workspace agent list, `AgentIdentity` + `RuntimeBinding` status, provider connection summary (redacted), native/specialist lanes | Create agent profile (supervisor), pin/unpin lanes, open settings sheets | **CellAuthorityGate** for install-scoped mutations; **RunAuthorityGate** not required for list-only | **Manual:** agent lane renders after login without first chat (`dogfood-install-gate` wizard step). **Harness:** `web-build` (panel bundle present). **Future:** `surface-agent-rail` scenario |
| **Chat** | Room/session binding, Hermes message history, model picker catalog, run/stop state | Send message, bind/new session, stop/steer turn, slash dispatch | **RunAuthorityGate** before stream (WF-009); lease via `turn_credentials` today | **Manual:** `dogfood-install-gate` — first chat after wizard. **Harness:** `api-oauth-llm`, `api-provider-models`. **Future:** `surface-chat-run-receipt` |
| **Files** | File tree under generated `Files/` (`/workspace`), file content metadata | Read, write, upload, delete within workspace mount | **CellAuthorityGate** for path escape; session auth on API routes; run-scoped writes deferred (WF-NS-P5) | **Manual:** file roundtrip in dogfood. **Harness:** `api-typecheck` (API compiles). **Future:** `surface-files-sandbox` — prove no path outside `Files/` |
| **Browser** | Workspace artifact preview (HTML, Markdown, static assets from `Files/`) | None (preview-only v0.1.x) | Same read boundary as Files; no arbitrary URL fetch | **Manual:** open generated HTML/Markdown artifact after file write. **Harness:** `web-build`. **Future:** `surface-browser-sandbox` |
| **Activity** | Room-scoped events (`GET /api/rooms/:id/activity`), run/file/chat summaries | None (read-only feed) | Session auth; events must not leak cross-user credentials (public mode) | **Manual:** event visible after chat or file action in dogfood. **Harness:** none yet. **Future:** `surface-activity-events` tied to `RunEvent` (WF-NS-P2) |

## Gate mapping

```text
Surface open/render     -> session auth (+ deployment mode for public routes)
File/browser read/write -> CellAuthorityGate path policy (install root + Files mount)
Chat/run/stream         -> RunAuthorityGate -> Grant -> Lease -> runtime
Activity display        -> RunEvent stream (WF-NS-P2); no write path
```

## Evidence tiers

| Tier | Meaning | Examples |
|------|---------|----------|
| **Harness green** | Automated in `.harness/feature_list.json` or CI | `web-build`, `api-typecheck`, `dogfood-install-gate` |
| **Manual dogfood** | Maintainer sign-off script + browser | `sign-off-install.ps1`, wizard + chat |
| **Future scenario** | Dedicated surface scenario not yet in harness | `surface-*` rows above |

## Non-goals (v0.1.x)

- Host Claude/Codex/Cursor execution surfaces
- Billing-grade run receipts (WF-016)
- Adapter-neutral skills/slash semantics (WF-013/NS-P4 deferred)

## Sources

- `archive/planning/living-audit/workframe-surface-baseline.md`
- `docs/public/using-workframe.md`
- WF-039 domain types (`RunSurface`, `Run`, `RunEvent`)

## Acceptance

See `backlog.json` → `WF-010.acceptance`.
