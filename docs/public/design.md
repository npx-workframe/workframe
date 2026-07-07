---
version: alpha
name: Workframe UI
description: Global semantic design system for apps/web — theme-invariant tokens and chrome contracts. Per-theme palettes live in dark-design.md, neo-design.md, blueprint-design.md.
source_truth:
  - apps/web/src/styles/tokens/
  - apps/web/src/styles/components/canvas.css
themes:
  - dark-design.md
  - neo-design.md
  - blueprint-design.md
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

**last_verified:** 2026-07-07 · **CSS truth:** `apps/web/src/styles/tokens/` + `themes/*.css`

Agents doing cosmetic UI work: read this file first, then the active theme doc. Copy rules: [`docs/ledger/copy-style-notes.md`](../ledger/copy-style-notes.md). UI lane boundaries: [`docs/ledger/handoffs/cosmetic-ui-lane.md`](../ledger/handoffs/cosmetic-ui-lane.md).

## Overview

Workframe is a dense workspace shell (header, rails, docked panels, chat, activity). Visual identity is **token-driven**: components use `--wf-*` CSS variables, not hard-coded colors. Three shipped themes (`dark`, `neo`, `blueprint`) share the same semantic vocabulary; each theme file sets palette + chrome feel.

**Layer stack (bottom → top):**

1. `body` — `--wf-bg` solid base (`base.css`)
2. `.wf-canvas` — gradient, orbs, overlay, grid (`canvas.css`; values per theme)
3. `.wf-shell` — transparent chrome; panels opt into surface fill

**Chrome modes** (`--wf-chrome-mode` on `[data-theme]`):

| Mode | Themes | Behavior |
|------|--------|----------|
| `line` | `dark` | Visible `--wf-border` lines; flat `--wf-shadow-*`; neo relief tokens inert |
| `relief` | `neo`, `blueprint` | Borderless edges; depth via `--wf-neo-*` shadow stacks |

**Workspace chrome fill** (`--wf-workspace-chrome-fill`): unset/surface = raised panels (neo default); `transparent` = blueprint workspace panels show moleskine grid through.

## Colors (semantic)

Themes must define every token in `palette-contract.css`. Global wiring in `semantic.css`:

| Token | Role |
|-------|------|
| `--wf-bg`, `--wf-text`, `--wf-muted` | Page base and copy hierarchy |
| `--wf-border`, `--wf-border-strong` | Structural edges (line mode) |
| `--wf-surface`, `--wf-surface-soft` | Panel / card fills |
| `--wf-primary`, `--wf-primary-foreground` | Primary actions and inverse |
| `--wf-violet`, `--wf-violet-glow`, `--wf-cyan`, `--wf-mint`, `--wf-ring` | Accent family + focus ring |
| `--wf-accent` | Alias → `--wf-violet` |
| `--wf-error`, `--wf-success`, `--wf-warning` (+ soft variants) | Status (blueprint remaps some to white — see theme doc) |
| `--wf-notice-*`, `--wf-status-fg` | Inline notices and status copy |

Chrome border scale (`chrome-contract.css`) — each theme sets `--wf-chrome-border-solid` through `--wf-chrome-border-ghost` as mixes of `--wf-border` (dark) or `transparent` (relief themes).

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
| `--wf-blur` | 34px (backdrop blur surfaces) |

**Scroll gutters** (`foundation.css`, `scroll-area.css`):

- `--wf-scroll-gutter-inline` = 8px; `--wf-scroll-gutter-block` = 16px
- `--wf-panel-scroll-inset` = 4px before scrollbar track
- Scrollbar: 6px thumb + 2px inset each side → 10px track
- Use class `wf-scroll` or `ScrollArea` — flush top/left; gutter on inline-end/block-end

## Elevation & depth

**Line mode (dark):** `--wf-shadow-sm` … `--wf-shadow-xl`, `--wf-shadow-inset`; controls use thin glass borders + hover fill.

**Relief mode (neo, blueprint):** `--wf-relief-shadow-color/alpha`, `--wf-relief-highlight-color/alpha` compose `--wf-neo-flat`, `--wf-neo-highlight`, inset pairs. Controls default flush; hover/active use `--wf-control-shadow-raised`.

**Canvas depth:** orbs (blur 130px), `--wf-overlay`, optional pixel grid or blueprint moleskine lines — per theme doc.

## Shapes

**Radius knobs** (`radius.css`): `--wf-radius-knob-sm` (4px), `md` (8px default / 4px in themes), `lg` (12px).

**Component mapping:** `--wf-radius-control`, `--wf-radius-surface`, `--wf-radius-tool-btn`, `--wf-radius-shell`, etc. derive from knobs.

**Border width:** `--wf-border-width` — 1px (dark), 2px (neo/blueprint relief).

## Components (global vocabulary)

| Surface | Class / pattern | Notes |
|---------|-----------------|-------|
| App shell | `.wf-shell`, `.wf-shell__header` | Transparent over canvas; theme sets header chrome |
| Canvas | `.wf-canvas`, `CanvasBackground.tsx` | Fixed layer; no pointer events |
| Panels | `.wf-panel`, `PanelShell` | Scroll via `wf-scroll` / `ScrollArea` |
| Floating lists | `.wf-floating-menu` | Glass blur menus |
| Composer tools | `.wf-composer`, `.wf-tool-btn` | 28px tool buttons |
| Activity | `.wf-activity-tree`, `.wf-tool-run` | Tree rows + expandable tool runs |
| Dialog | `Dialog` / `DialogContent` | Centered panel with header/close |
| Modal | Backdrop blur full-screen | Not a centered dialog sheet |
| Theme lab | `/dev/theme`, `?wf-dev=theme` | `ThemeShowcasePage` — token preview |

**Product copy:** UI says **Workframe**, not "workspace" (except internal IDs). See `copy-style-notes.md`.

**shadcn:** Blueprint maps `--background`, `--card`, `--popover`, etc. to `--wf-*` in its theme block; other themes use Workframe tokens directly in component CSS.

## Theme index

| Theme | Doc | CSS | Chrome | Character |
|-------|-----|-----|--------|-----------|
| Dark | [dark-design.md](dark-design.md) | `themes/dark.css` | `line` | Dark glass, violet/cyan orbs, visible borders |
| Neo | [neo-design.md](neo-design.md) | `themes/neo.css` | `relief` | Light soft UI, neo-morphic shadows |
| Blueprint | [blueprint-design.md](blueprint-design.md) | `themes/blueprint.css` | `relief` + transparent workspace | Engineering blue, moleskine grid |

Switch via `ThemeSwitcher`; options in `apps/web/src/lib/themeOptions.ts`.

## Do's and Don'ts

**Do**

- Change colors via `themes/*.css` `[data-theme]` blocks — keep `palette-contract.css` parity across themes
- Use existing `--wf-*` tokens before adding new ones
- Match chrome mode: don't add visible borders in relief themes or flat shadows in dark line mode
- Keep scroll surfaces on `wf-scroll` gutter discipline
- Preview token changes in Theme Showcase (`pnpm dev:web` → `/dev/theme`)

**Don't**

- Hard-code hex in component CSS when a semantic token exists
- Mix behavioral/React wiring in cosmetic passes (see cosmetic-ui-lane off-limits)
- Add themes without defining the full palette + chrome contract
- Use full-screen sheets for settings — use `Dialog`/`DialogContent` in rails
- Invent new accent hues outside the theme's violet/cyan/mint (blueprint uses white-on-blue)
