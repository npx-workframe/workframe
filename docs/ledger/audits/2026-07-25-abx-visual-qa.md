# ABX visual QA audit — 2026-07-25

**Campaign:** WF-UI-004 / WF-UI-005 / WF-UI-006  
**Install:** ABX slot 2 — UI `http://127.0.0.1:28644`, API `http://127.0.0.1:29120`  
**Package:** `create-workframe@0.1.27` (pending publish; built from commits through `d84f34a`, `24509ca`)  
**Scope:** UI/CSS/tokens only — no LLM chat, no backend changes, no credentials in files.

## Environment

| Check | Result |
|-------|--------|
| API health | `ok: true`, `install_window_open: true`, `deployment_mode: trusted_team` |
| Wizard resume | `resume_step: smtp` (steps 1–3 complete; blocked at email delivery) |
| Admin email | Pre-filled from prior session (not entered during this QA) |
| SMTP | Not configured — intentionally not filled (browser-only policy) |

## Design-system discipline (consume, not invent)

Authority: [`docs/public/design.md`](../../public/design.md) ownership table.

| Layer | Owner | Workframe rule |
|-------|--------|----------------|
| Palettes, radii, relief L/S, glass grammar | Architectonic `generated/` | Never hand-edit; `npm run sync:design-system` |
| `--wf-*` aliases | `bridge.css`, `relief-primitives.css` | Product CSS reads aliases only |
| Layout (wizard grid, rails, Dockview) | `styles/components/` | No per-theme selectors; use `data-chrome-mode` / axes from `applyTheme()` |
| Chrome mode | `theme.ts` | `shadows`→relief, `glass`→glass, `lines`→line |

**This session’s patches follow that boundary:**

| Patch | Scope (14 themes × breakpoints) | Token / source |
|-------|----------------------------------|----------------|
| Wizard high relief | Neo Light/Dark only (`data-chrome-mode='relief'`) | `--wf-relief-outset-l` (same as dialog; was wrongly `--wf-relief-inset-l`) |
| Theme step 2-col grid | All 14 on wizard theme step; ≤480px → 1 col | Workframe layout; swatches stay Architectonic |
| Inactive disabled CTA | All 14 (SMTP footer, etc.) | `data-tone='inactive'` uses `--wf-btn-fg-inactive`; no extra `opacity: 0.45` |

Structural contrast/radius bugs in theme CSS → upstream Architectonic. Overlay trap, rail gating, provider SVG paths → Workframe components.

## Tooling note

`plugin-browse-browser` MCP failed on Windows (`spawn …/browse ENOENT`; daemon socket `EACCES`). QA completed via Playwright (same browse-cli stack) with headless Chrome. Screenshots saved under `docs/ledger/audits/screenshots/2026-07-25-abx/`.

## Themes tested (14 visible)

All 14 picker themes screenshot at desktop **1280×800** and mobile **390×844** on the theme step:

`minimal-light`, `minimal-dark`, `neo-light`, `neo-dark`, `brutalist-light`, `brutalist-dark`, `liquid-glass-light`, `liquid-glass-dark`, `frosted-glass-light`, `frosted-glass-dark`, `bauhaus`, `newspaper`, `notebook`, `blueprint`

Hidden themes (`mono`, `neo-color`, `minimal-color`, `leather-book`) — **not present** in picker or header switcher dropdown. ✓

## Screen matrix

| Surface | Desktop | Mobile | Notes |
|---------|---------|--------|-------|
| Welcome (step 1) | ✓ | ✓ | Admin email field visible when navigated back |
| Theme picker (step 2) | ✓ | ✓ | All 14 themes + per-theme shots |
| Deployment (step 3) | ✓ | ✓ | Four mode cards; Cloud disabled |
| Email delivery (step 4) | ✓ | ✓ | Current resume step |
| Verify email (step 5) | dup | dup | **Blocked** — rail nav did not advance panel |
| Workframe profile (6) | dup | dup | **Blocked** |
| Billing (7) | dup | dup | **Blocked** |
| Integrations (8) | dup | dup | **Blocked** — provider logos not reachable |
| Profile (9) | dup | dup | **Blocked** |
| Agent (10) | dup | dup | **Blocked** |
| Agent model (11) | dup | dup | **Blocked** — connect UI not reachable |
| Team invites (12) | dup | dup | **Blocked** |
| Theme switcher dropdown | ✓ | ✓ | Open-state capture on SMTP step |

`dup` = sidebar label clicked but main panel remained on SMTP (wizard `maxReachableIndex` gate).

## Findings

| ID | Severity | Area | Finding |
|----|----------|------|---------|
| QA-01 | **high** | Wizard gating | Steps 5–12 not reachable while `resume_step=smtp` and SMTP untested. Forward rail clicks on Integrations / Agent model do not change the main panel — screenshots for those steps are duplicates of SMTP. **Provider brand logos on connect screens could not be verified in-context.** |
| QA-02 | **high** | Theme switcher / mobile | Open theme-switcher dropdown on mobile (390px) overlaps the step-indicator grid and obscures wizard content (see `13-theme-switcher-dropdown-mobile-390x844.png`). Dropdown needs higher z-index isolation or dismiss-on-outside-tap with layout push. |
| QA-03 | **medium** | Mobile step rail | Step-indicator grid on mobile uses mixed dots and numbers with uneven spacing (theme + SMTP steps). Hard to scan progress (see `02-theme-picker-mobile`, `04-smtp-mobile`). |
| QA-04 | **medium** | Wizard rail UX | Sidebar items beyond `maxReachableIndex` look listed but are not navigable; clicking Integrations/Billing while on SMTP leaves panel unchanged with no toast — misleading affordance. |
| QA-05 | **medium** | Wizard rail / step count | Header shows **“STEP X OF 12”** but left rail only surfaces **9** numbered items at this deployment mode; agent / agent-model / team steps not visible until later (or missing from rail). Confusing progress semantics. |
| QA-06 | **medium** | Sidebar focus | On SMTP step, **Billing Model** rail item shows an active/raised neo highlight despite not being the current step (`integrations-recheck-desktop.png`). Possible erroneous `configured`/focus styling. |
| QA-07 | **low** | Blueprint / mobile SMTP | Disabled **Continue to verification** button is low-contrast on blueprint dark grid (`04-smtp-mobile`). |
| QA-08 | **low** | Glass themes | Liquid/frosted glass theme previews produce very large PNG captures (up to ~470 KB desktop) — heavy blur/stacking may impact low-end mobile GPU; worth perf spot-check. |
| QA-09 | **info** | Tooling | Cursor Browse MCP unusable on this Windows host without shim fix; document for future QA runs. |

### Provider logos (integrations / connect)

**Not verified** — wizard blocked before Integrations and Agent model steps. Static brand SVGs are bundled (not served at `/assets/brands/*.svg`). In-page `BrandMark` rendering on connect rows remains untested this run.

**Recommended follow-up:** complete SMTP with a throwaway test inbox *in browser only*, or reset install to `single_user_local` to skip SMTP and reach Integrations sooner.

## Theme visual pass (spot-check)

| Theme family | Desktop | Mobile | Issues |
|--------------|---------|--------|--------|
| Lines (minimal) | ✓ | ✓ | None noted |
| Neo | ✓ | ✓ | Neumorphic shadows consistent |
| Brutalist | ✓ | ✓ | High-contrast borders readable |
| Glass (liquid/frosted) | ✓ | ✓ | Previews render; large compositing cost (QA-08) |
| Custom (bauhaus, newspaper, notebook, blueprint) | ✓ | ✓ | Notebook grid background applies to page chrome |

## Artifacts

- Screenshots: `docs/ledger/audits/screenshots/2026-07-25-abx/` (62 PNGs)
- Automation scripts (local QA helpers): `run-visual-qa.mjs`, `recheck-integrations.mjs` in same folder

## Fix rounds

| Round | Commit | Files | Themes / breakpoints |
|-------|--------|-------|-------------------|
| R1 | `d84f34a` | `relief-surfaces.css`, `onboarding.css`, `theme-picker.css`, `action-btn.css` | Neo relief wizard; theme grid all 14; inactive CTA all 14 |
