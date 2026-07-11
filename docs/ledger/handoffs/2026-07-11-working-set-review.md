# Handoff — working-set bug/consistency review (2026-07-11)

**Role:** architect (Claude adapter, review only — no fixes applied)
**Scope reviewed:** uncommitted working tree at `main` (87 modified, 9 untracked, 6 deleted files) on top of unpushed commit `1ec9efd` (fix(api): start profile gateway before session create on bind).
**Verification run:** `pytest` (services/workframe-api), `tsc -b` (apps/web), `eslint .` (apps/web), `node services/workframe-api/run-typecheck.mjs`, `pnpm verify:public`.

## Verdicts

- `tsc -b` (apps/web): **green**
- `run-typecheck.mjs`: **green**
- `pnpm verify:public`: **green**
- `pytest`: **3 failed, 67 passed, 1 collection error**
- `eslint`: **152 errors / 11 warnings**

## Findings (ranked)

### 1. Test pollution: `sys.modules["server"]` replacement breaks the suite (P1)

`test_model_surface_consistency.py:24` does `sys.modules["server"] = server` with its own importlib-loaded instance (bound to its temp env) and never restores it. Pytest imports all test modules at collection before running, so every later `import server` / `_srv()` inside product modules resolves to that stale instance. Consequences observed:

- `test_local_bootstrap.py` — both tests fail in the full run (403 instead of 400/200) because they patch `DEPLOYMENT_MODE` on the module they imported, while `handler_auth._srv()` resolves the replaced one. **Both pass in isolation.**
- `test_user_llm_prefs.py` (new, untracked) — crashes at collection with `sqlite3.OperationalError: no such table: users`: its `user_prefs` calls `_srv()` → replaced server → different/uninitialized DB.

Fix direction: make `test_model_surface_consistency.py` restore `sys.modules["server"]` (try/finally or fixture), or stop aliasing globally and inject the instance explicitly.

### 2. `test_user_llm_prefs.py` contains no test functions (P1)

It is script-style (module-level asserts + `print`). Run alone, pytest collects **nothing** (`no tests ran`, exit 5) — it only "runs" as an import side effect during collection. Wrap the body in `def test_...()` functions (and drop the module-level DB writes into fixtures/setup). Until then it provides zero coverage and destabilizes collection (see finding 1).

### 3. Stale assertion in `test_run_ledger.py::test_schema_and_round_trip` (P1)

Working-set change to `run_ledger.list_run_events_for_room` now intentionally skips `run.authorized` events (activity-feed noise reduction), but the test still asserts `len(events) >= 2` at `test_run_ledger.py:91`. Fails even in isolation. Update the assertion (expect 1 `run.completed`, or assert `run.authorized` is filtered) — or revisit the filter if authorized events were meant to stay visible.

### 4. Half-migrated web error handling: `throw info` plain object (P1)

`apps/web/src/lib/apiClient.ts` `parseJson` changed from `throw new Error(noticeMessage(...))` to `throw info` — a plain `WorkframeNoticeInfo`, not an `Error`.

- `formatWorkframeError` handles it (`'message' in err && 'tone' in err`), so paths routed through it are fine.
- But ~42 catch sites across ~29 files still use `err instanceof Error ? err.message : '<generic fallback>'` (e.g. `ChatSettingsSheet.tsx:198,297,314,412`). Every rejection from the 9 apiClient-based modules (`chatApi`, `filesApi`, `workframeRoutes`, `workframeAgentsApi`, `activityFeed`, `snapshotApi`, `hermesCatalogApi`, `hermesDashboardApi`, `workframeMetaApi`) now shows the generic fallback instead of the server message at those sites. Stack traces are also lost.
- The `${method} ${path}` context was dropped (`_method`/`_path` unused params, flagged by lint).

Recommendation: throw a `WorkframeApiError extends Error` that carries the notice payload — keeps `instanceof Error` sites working and preserves the notice for `formatWorkframeError`/toasts. Otherwise migrate all catch sites in the same change.

### 5. Harness ledger contradicts local reality (P2)

`.harness/feature_list.json` (working set) flips `api-typecheck` and `public-repo-verify` to `passes: false` (updated 2026-07-10), but **both pass locally** as of this review. Either the flips reflect a cursor-cloud environment issue or they are stale pessimism — re-run in the owning environment and reconcile before commit.

### 6. Lint is red, including working-set files (P2)

`pnpm -C apps/web lint`: 152 errors. In files this working set touches: `apiClient.ts` (unused `_method`/`_path` — falls out of finding 4), `workframeErrors.ts:407` (`no-useless-assignment` — the `let text = ''` / try-reassign pattern), `workframeAuthApi.ts:539` (`preserve-caught-error`). Many others look pre-existing (`no-control-regex` in `workframeProfile.ts`, etc.). Decide whether lint is a gate; if yes it needs a dedicated pass.

### 7. Commit hygiene (P2)

- The 9 untracked files (AgentInstructionsFields, IntegrationsStack, SignInAppField, ProfileEntityCardGrid, WorkframeErrorToast, sonner.tsx, workframeErrorToast.tsx, workframe-toast.css, test_user_llm_prefs.py) are imported by tracked modified files — they **must land in the same commit** or the build breaks. `sonner@^2.0.7` was added to package.json + lockfile — OK.
- Commit `6d48f50` on main is literally titled `temp` and is already pushed history — noted for the record; do not rewrite pushed history.
- Nearly every modified file warns `LF will be replaced by CRLF` — check `.gitattributes`/`core.autocrlf` before committing from Windows to avoid a noisy line-ending diff.

### 8. Minor smells (P3, no action required)

- `chat_stream.py`: `model=str(model_name if not last_classified_error else "")` — safe (short-circuit means `model_name` is never evaluated when unbound) but reads like a NameError; restructure when touching next.
- Deleted files (`DeviceCodeOAuthDialog.tsx`, `mockCrew.ts`, `doctor-repair.mjs`, `wf032_*.py`) verified: **no dangling references**.

## Suggested execution order (Cursor)

1. Fix finding 1 (restore `sys.modules["server"]`) + finding 2 (real test functions) + finding 3 (assertion) → full pytest green.
2. Decide the `throw info` contract (finding 4) and apply consistently; re-run lint on touched files.
3. Re-run harness scenarios in the owning environment; reconcile `.harness/feature_list.json` (finding 5).
4. Commit the working set as coherent WF-scoped commits including the 9 untracked files; verify line endings.

## Evidence

- Full pytest run 2026-07-11: `3 failed, 67 passed` (`test_local_bootstrap` ×2, `test_run_ledger` ×1) + `test_user_llm_prefs.py` collection error.
- `test_local_bootstrap` passes in isolation and when paired with `test_run_ledger` — pollution confirmed order-dependent.
- `tsc -b` exit 0; `eslint .` exit 1 (152 errors); `run-typecheck.mjs` and `pnpm verify:public` exit 0.
