# Handoff — Cosmetic UI lane (parallel)

**Created:** 2026-07-05  
**Owner:** Human + cosmetic-ui agent (parallel)  
**Main track owner:** implementation agent (backlog → deferred, precise WF commits)

## Goal

Visual polish only — spacing, typography, colors, icons, glass/blur, scroll gutters, copy tone. **No behavior or API contract changes.**

## Yes — work in parallel

Cosmetic UI is a **separate lane**. It does not block and should not be blocked by API/server/backlog commits on `main`, as long as you stay inside the boundaries below.

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
cd D:\ab\projects\workframe
pnpm dev:web
# Preview: dogfood at http://127.0.0.1:18644 after main track syncs; for Vite-only cosmetic, localhost:5173 is enough
pnpm --filter @workframe/web lint
pnpm build:web
```

Do **not** restart Docker or copy to `MyBusiness/` unless the user asks — main track owns dogfood deploy.

## Git discipline

- Prefer a branch: `ui/cosmetic-<short-topic>`
- Commits: `style(web): <what> (WF-036 cosmetic)` — one visual theme per commit
- **Do not** mix functional fixes; if you need a behavior change, stop and hand back to main track
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

**2026-07-05** — Theme consolidation (WF-036 cosmetic)
- Kept `dark` + `neo` only; removed light, mono-light, mono-dark, brutal, architectonic (+ overrides)
- Standardized palette contract: `styles/tokens/theme-palette-contract.css`; matching token sets in `dark.css` / `neo.css`
- Updated `theme.ts`, `themeOptions.ts`, `useTheme.ts`, `index.html`, `shadcn-theme.css`, `highlight-themes.css` (neo = light syntax)
- Files: `apps/web/src/styles/**`, `apps/web/src/lib/theme*.ts`, `apps/web/src/hooks/useTheme.ts`, `apps/web/index.html`, `apps/web/src/main.tsx`, `apps/web/src/index.css`
- `pnpm build:web` ✓
