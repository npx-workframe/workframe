---
version: alpha
name: Workframe UI
description: Global semantic design system for apps/web — theme-invariant tokens and chrome contracts. Per-theme palettes live in strato-dark-design.md, neo-light-design.md, neo-blue-design.md.
source_truth:
  - apps/web/src/styles/tokens/
  - apps/web/src/styles/components/canvas.css
  - apps/web/src/components/shell/canvas/
  - apps/web/src/lib/canvas-layers.ts
themes:
  - strato-dark-design.md
  - neo-light-design.md
  - neo-blue-design.md
typography:
  body-md:
    fontFamily: Inter Tight
    fontSize: 13px
    fontWeight: 400
    lineHeight: 20px
  ui:
    fontFamily: Inter Tight
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  caption:
    fontFamily: Inter Tight
    fontSize: 11px
spacing:
  space-1: 4px
  space-2: 8px
  space-4: 16px
rounded:
  knob-sm: 4px
  knob-md: 8px
  knob-lg: 12px
  pill: 999px
---

# Workframe UI — Global design system

**last_verified:** 2026-07-12 · **CSS truth:** `apps/web/src/styles/tokens/` + `themes/*.css` + `components/shell/canvas/`

Agents doing cosmetic UI work: read this file first, then the active theme doc. Copy rules: [`docs/ledger/copy-style-notes.md`](../ledger/copy-style-notes.md). UI lane boundaries: [`docs/ledger/handoffs/cosmetic-ui-lane.md`](../ledger/handoffs/cosmetic-ui-lane.md).

## Overview

Workframe is a dense workspace shell (header, rails, docked panels, chat, activity). Visual identity is **token-driven**: components use `--wf-*` CSS variables, not hard-coded colors. Three shipped themes (`strato-dark`, `neo-light`, `neo-blue`) share the same semantic vocabulary; each theme file sets palette + chrome feel.

Themes compose four layers (bottom → top):

| Layer | What | Source |
|-------|------|--------|
| **1. Color** | Solid `--wf-bg` on `body` + `AtmosphereBg` (gradient/orbs/vignette only in line mode) | `base.css`, `AtmosphereBg.tsx`, per-theme canvas tokens |
| **2. Texture** | Full-viewport repeating pattern (`DotGrid` or `MoleskineGrid`) | `canvas-layers.ts`, `DotGrid.tsx` / `MoleskineGrid.tsx`, `canvas.css` |
| **3. Shell** | Borders + flat shadows (line) or solid `--wf-bg` surfaces with L/S shadow stacks (relief) | `--wf-chrome-mode`, `relief-primitives.css`, `relief-surfaces.css` |
| **4. Theme** | Palette, texture ink, typography, shell family | `themes/*.css` |

**Formula:** base color + optional texture + shell treatment = theme. Relief chrome uses solid `--wf-bg` fills and shadow geometry; relief mode also disables atmosphere gradients, orbs, overlays, and texture bleed. Neo Light and Neo Blue currently omit the texture layer; Strato Dark uses `DotGrid`.

## Canvas stack

`CanvasBackground` (`components/shell/canvas/CanvasBackground.tsx`) mounts on every route (workspace, onboarding, auth). Mapping in `lib/canvas-layers.ts`:

| Theme | Texture component |
|-------|-------------------|
| `strato-dark` | `DotGrid` |
| `neo-light`, `neo-blue` | *(none — flat solid canvas in relief mode)* |

`DotGrid` and `MoleskineGrid` remain available components; wire them per theme via `getThemeCanvasTexture()` in `canvas-layers.ts`.

```text
.wf-canvas (fixed, z-index 0)
├── AtmosphereBg     — color only
└── DotGrid | MoleskineGrid   — texture only (z-index 4, above atmosphere)
```

**Dot grid mechanics** (`canvas.css`): theme sets ink (`--wf-dot-grid-rgb`, `--wf-dot-grid-opacity`, `--wf-dot-grid-tile`); CSS mask defines one dot per tile. Vignette belongs on `AtmosphereBg__overlay`, not on the dot layer.

**Moleskine mechanics** (`canvas.css`): repeating 1px lines on `--wf-moleskine-grid-tile` with `--wf-moleskine-grid-line`.

`applyTheme()` in `lib/theme.ts` sets `data-theme` and `data-chrome-mode` on `<html>` (mirrored for CSS selectors).

## Chrome modes

| Mode | Themes | `--wf-chrome-fill` | Behavior |
|------|--------|-------------------|----------|
| `line` | `strato-dark` | `var(--wf-surface)` | Visible `--wf-border` lines; flat `--wf-shadow-*` |
| `relief` | `neo-light`, `neo-blue` | `var(--wf-bg)` | Borderless; solid surfaces with depth via L/S relief stacks |

Relief primitives (`relief-primitives.css`):

| Size | Offset | Blur | Use |
|------|--------|------|-----|
| **L** | 4px | 8px | Wizard/dialog/auth shells, large wells |
| **S** | 3px | 6px | Controls, tabs, buttons, fields |

Per-theme tuning: `--wf-relief-shadow-rgb`, `--wf-relief-shadow-alpha`, `--wf-relief-highlight-rgb`, `--wf-relief-highlight-alpha`. Shared chrome overrides live in `relief-surfaces.css` (not duplicated per theme file).

Legacy alias: `--wf-workspace-chrome-fill` → `--wf-chrome-fill`.

## Colors (semantic)

Themes must define every token in `palette-contract.css`. Global wiring in `semantic.css`:

| Token | Role |
|-------|------|
| `--wf-bg`, `--wf-text`, `--wf-muted` | Page base and copy hierarchy |
| `--wf-border`, `--wf-border-strong` | Structural edges (line mode) |
| `--wf-surface`, `--wf-surface-soft` | Panel / card fills (line mode and solid relief chrome) |
| `--wf-chrome-fill` | Interactive + shell surface fill above texture |
| `--wf-primary`, `--wf-primary-foreground` | Primary actions and inverse |
| `--wf-violet`, `--wf-violet-glow`, `--wf-cyan`, `--wf-mint`, `--wf-ring` | Accent family + focus ring |
| `--wf-accent` | Alias → `--wf-violet` |
| `--wf-error`, `--wf-success`, `--wf-warning` (+ soft variants) | Status (Neo Blue remaps some to white — see theme doc) |
| `--wf-notice-*`, `--wf-status-fg` | Inline notices and status copy |

Texture tokens (per theme): `--wf-dot-grid-tile`, `--wf-dot-grid-rgb`, `--wf-dot-grid-opacity`; Neo Blue adds `--wf-moleskine-grid-tile`, `--wf-moleskine-grid-line`.

Chrome border scale (`chrome-contract.css`) — each theme sets `--wf-chrome-border-solid` through `--wf-chrome-border-ghost` as mixes of `--wf-border` (Strato Dark) or `transparent` (relief themes).

## Typography

**Families** (`foundation.css`): `--wf-font-sans` = Inter Tight stack; `--wf-font-mono` = JetBrains Mono stack.

**Scale** (theme-invariant):

| Token | Size | Leading |
|-------|------|---------|
| `--wf-type-micro` | 9px | 12px |
| `--wf-type-meta` | 10px | 12px |
| `--wf-type-caption` | 11px | 16px |
| `--wf-type-ui` | 12px | 16px |
| `--wf-type-body` | 13px | 20px |

Prefer `var(--wf-type-*)` in components; avoid raw `px` for workspace chrome.

## Layout & spacing

**Grid:** `--wf-space-1` (4px), `--wf-space-2` (8px), `--wf-space-4` (16px).

**Shell dimensions** (`foundation.css`):

| Token | Value |
|-------|-------|
| `--wf-header-height` | 56px |
| `--wf-footer-height` | 28px |
| `--wf-panel-header-height` | 32px |
| `--wf-rail-width-collapsed` / `expanded` | 52px / 200px |
| `--wf-shell-width` / `--wf-shell-height` | 840px / 540px (onboarding + settings dialog) |
| `--wf-blur` | 34px (backdrop blur surfaces) |

**Scroll gutters** (`foundation.css`, `scroll-area.css`):

- `--wf-scroll-gutter-inline` = 8px; `--wf-scroll-gutter-block` = 16px
- `--wf-panel-scroll-inset` = 4px before scrollbar track
- Scrollbar: 6px thumb + 2px inset each side → 10px track
- Use class `wf-scroll` or `ScrollArea` — flush top/left; gutter on inline-end/block-end

## Elevation & depth

**Line mode (Strato Dark):** `--wf-shadow-sm` … `--wf-shadow-xl`, `--wf-shadow-inset`; controls use thin glass borders + hover fill on `--wf-chrome-fill` (surface).

**Relief mode (Neo Light, Neo Blue):** dual shadow stacks from `--wf-relief-*` primitives over solid `--wf-bg` surfaces. Wizard shell uses inset **L**; modals/dialogs use outset **L**; controls use **S**.

## Shapes

**Radius knobs** (`radius.css`): `--wf-radius-knob-sm` (4px), `md` (8px default / 4px in themes), `lg` (12px).

**Component mapping:** `--wf-radius-control`, `--wf-radius-surface`, `--wf-radius-tool-btn`, `--wf-radius-shell`, etc. derive from knobs.

**Border width:** `--wf-border-width` — 1px (Strato Dark), 2px (Neo relief themes).

## Components (global vocabulary)

| Surface | Class / pattern | Notes |
|---------|-----------------|-------|
| App shell | `.wf-shell`, `.wf-shell__header` | Transparent over canvas |
| Canvas | `.wf-canvas`, `CanvasBackground` | `AtmosphereBg` + texture component |
| Onboarding | `.wf-onboarding-page`, `.wf-onboarding-wizard` | Page transparent; same canvas as workspace |
| Panels | `.wf-panel`, `PanelShell` | Scroll via `wf-scroll` / `ScrollArea` |
| Floating lists | `.wf-floating-menu` | Glass blur menus |
| Composer tools | `.wf-composer`, `.wf-tool-btn` | 28px tool buttons |
| Activity | `.wf-activity-tree`, `.wf-tool-run` | Tree rows + expandable tool runs |
| Dialog | `Dialog` / `DialogContent` | Centered panel with header/close |
| Modal | Backdrop blur full-screen | Not a centered dialog sheet |
| Theme lab | `/dev/theme`, `?wf-dev=theme` | `ThemeShowcasePage` — token preview |

**Product copy:** UI says **Workframe**, not "workspace" (except internal IDs). See `copy-style-notes.md`.

**shadcn:** Neo Blue maps `--background`, `--card`, `--popover`, etc. to `--wf-*`; relief mode sets `--card` / `--popover` to `--wf-chrome-fill` (transparent).

## Theme index

| Theme | Slug | Doc | CSS | Chrome | Texture | Character |
|-------|------|-----|-----|--------|---------|-----------|
| Strato Dark | `strato-dark` | [strato-dark-design.md](strato-dark-design.md) | `themes/strato-dark.css` | `line` | `DotGrid` | Dark glass, violet/cyan orbs, visible borders |
| Neo Light | `neo-light` | [neo-light-design.md](neo-light-design.md) | `themes/neo-light.css` | `relief` | — | Light soft UI, solid chrome, relief shadows |
| Neo Blue | `neo-blue` | [neo-blue-design.md](neo-blue-design.md) | `themes/neo-blue.css` | `relief` | — | Engineering blue, solid relief chrome |

Switch via `ThemeSwitcher`; options in `apps/web/src/lib/themeOptions.ts`.

## Do's and Don'ts

**Do**

- Change colors via `themes/*.css` `[data-theme]` blocks — keep `palette-contract.css` parity across themes
- Use existing `--wf-*` tokens before adding new ones
- Keep texture on `DotGrid` / `MoleskineGrid` only — vignette on `AtmosphereBg`
- Match chrome mode: don't add visible borders in relief themes or flat shadows in Strato Dark line mode
- Keep scroll surfaces on `wf-scroll` gutter discipline
- Preview token changes in Theme Showcase (`pnpm dev:web` → `/dev/theme`)

**Don't**

- Hard-code hex in component CSS when a semantic token exists
- Assume atmosphere or texture shows through relief chrome (relief mode uses solid `--wf-bg` surfaces)
- Put vignette masks on the dot grid layer (masks define dot shape only)
- Mix behavioral/React wiring in cosmetic passes (see cosmetic-ui-lane off-limits)
- Add themes without defining the full palette + chrome contract
- Use full-screen sheets for settings — use `Dialog`/`DialogContent` in rails
- Invent new accent hues outside the theme's violet/cyan/mint (Neo Blue uses white-on-blue)
