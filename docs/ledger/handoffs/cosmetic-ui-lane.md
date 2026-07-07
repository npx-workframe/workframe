# Handoff — Cosmetic UI lane (parallel)

**Created:** 2026-07-05 · **Updated:** 2026-07-07  
**Owner:** Human + cosmetic-ui agent (parallel)  
**Main track owner:** implementation agent (backlog → deferred, precise WF commits)

## Goal

Visual polish only — spacing, typography, colors, icons, glass/blur, scroll gutters, copy tone. **No behavior or API contract changes.**

At this stage (2026-07-07) the lane is mostly **CSS refactoring and theme expansion** (e.g. blueprint theme, token architecture, canvas background layer) plus **minor global HTML adjustments** that are semantic and shared across all themes.

## Yes — work in parallel on `main`

Cosmetic UI is a **separate lane**. Multiple agents may commit to the same branch when each change is **surgical** — one visual concern per commit. Backend agents own API/server/ledger; UI agents own cosmetic `apps/web/` only. Lanes must not cross boundaries below.

## Boundaries (do not cross)

| Off limits | Why |
|------------|-----|
| `services/workframe-api/**` | Main track owns model routing, reconcile, WF-032/037 |
| `docs/ledger/backlog.json`, `orchestration.md` | Main track updates WF status |
| `apps/web/src/contexts/HermesSessionContext.tsx` | Session bind, new session, chat send |
| `apps/web/src/components/chat/Composer.tsx` | Model badge + send path |
| `apps/web/src/components/settings/ModelPickerPanel.tsx` | Model loading/save surface |
| `apps/web/src/lib/chatApi.ts`, `hermesCatalogApi.ts`, `agentProfile.ts` | API contracts |
| `apps/web/src/hooks/useSlashDispatcher.ts` | Command dispatch wiring |

## Safe zones

- `apps/web/src/**/*.css` — tokens, `wf-*` classes, scroll gutters
- Presentational components where you change **className / layout / copy only** (no new fetch, no new state for business logic)
- `apps/web/src/components/ui/**` — shadcn primitives (visual only)
- Panel chrome: `PanelHeader`, `PanelShell`, rails, toolbars (if no new API calls)
- Icons/avatars via existing `workframeAssets` / `brandAssets` — do not change provider resolution logic

## Backlog slot

**WF-036** (partial) — take only the **cosmetic** slice:

- Provider label display consistency (use `billingProviderDisplayLabel` — already exists; do not add new inference helpers)
- Scroll surfaces: `wf-scroll` / `ScrollArea` gutter rules per workspace AGENTS.md
- Dialog vs modal vocabulary (blur backdrop = modal; centered panel = dialog)
- Product copy says **Workframe**, not Workspace

Do **not** close WF-036 or edit backlog status — note your files in a short comment at the bottom of this handoff when done.

## Dev loop

```powershell
cd <workframe-repo>
pnpm dev:web
# Preview: dogfood at http://127.0.0.1:18644 after main track syncs; for Vite-only cosmetic, localhost:5173 is enough
pnpm --filter @workframe/web lint
pnpm build:web
```

Do **not** restart Docker or copy to `MyBusiness/` unless the user asks — main track owns dogfood deploy.

## Git discipline

- Same branch (`main`) is OK when commits stay surgical; optional branch: `ui/cosmetic-<short-topic>` for large sweeps
- Commits: `style(web): <what> (WF-036 cosmetic)` — one visual theme or token pass per commit
- **Do not** mix functional fixes; if you need a behavior change, stop and hand back to backend lane
- Do not commit unless user asks (same rule as main agent)

## Merge etiquette

1. Pull/rebase on latest `main` before large CSS sweeps.
2. If merge conflicts in shared components, **take main's logic** and re-apply your classes only.
3. Never revert `server.py` or session/model files to resolve conflicts — ask main track.

## Context (what main track just fixed — do not re-break)

- Codex chat: runtime `u-*` profiles use bare `gpt-5.4-mini` + `provider: openai-codex`, not OpenRouter proxy.
- Composer model badge loads without waiting for session bind.
- New session errors show in chat via `connectError`.

## Verify cosmetic work

- [ ] Hard refresh; no new console errors on chat open
- [ ] Model badge still shows provider + model (read-only)
- [ ] New session button still works
- [ ] Settings dialogs open/close; scroll gutters look correct
- [ ] `pnpm build:web` passes

## When done

Append under **Cosmetic log** below: date, files touched, screenshots optional, open questions.

---

## Cosmetic log

**2026-07-07** — Theme architecture pass (WF-036 cosmetic, parallel with backend on `main`)
- Added `blueprint` theme; `CanvasBackground` replaces atmosphere layer; `theme-architecture.css` token layout
- Files: `apps/web/src/styles/**`, `apps/web/src/components/shell/CanvasBackground.tsx`, `theme.ts`, `themeOptions.ts`
- Backend lane continued WF-032/API split in same push window — lane separation by path, not by branch

**2026-07-05** — Theme consolidation (WF-036 cosmetic)
- Kept `dark` + `neo` only; removed light, mono-light, mono-dark, brutal, architectonic (+ overrides)
- Standardized palette contract: `styles/tokens/theme-palette-contract.css`; matching token sets in `dark.css` / `neo.css`
- Updated `theme.ts`, `themeOptions.ts`, `useTheme.ts`, `index.html`, `shadcn-theme.css`, `highlight-themes.css` (neo = light syntax)
- Files: `apps/web/src/styles/**`, `apps/web/src/lib/theme*.ts`, `apps/web/src/hooks/useTheme.ts`, `apps/web/index.html`, `apps/web/src/main.tsx`, `apps/web/src/index.css`
- `pnpm build:web` ✓
