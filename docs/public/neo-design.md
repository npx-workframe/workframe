---
version: alpha
name: Workframe — Neo theme
parent: design.md
selector: "[data-theme='neo']"
source: apps/web/src/styles/themes/neo.css
color-scheme: light
chrome_mode: relief
colors:
  bg: "#e0e0e6"
  text: "#2a2a32"
  muted: "#7a7a86"
  border: transparent
  border_strong: "rgba(0, 0, 0, 0.08)"
  surface: "#e0e0e6"
  surface_soft: "rgba(224, 224, 230, 0.82)"
  primary: "#3a3a44"
  primary_foreground: "#e0e0e6"
  violet: "#7c6a9e"
  cyan: "#6a8e9e"
  mint: "#6a9e8a"
  ring: "rgba(124, 106, 158, 0.22)"
relief:
  shadow_rgb: "163 163 176"
  shadow_alpha: 0.24
  highlight_rgb: "255 255 255"
  highlight_alpha: 0.78
dot_grid:
  tile: 10px
  rgb: "42 42 50"
  opacity: 0.16
rounded:
  knob_sm: 4px
  knob_md: 4px
  knob_lg: 12px
  icon_btn: 50%
border_width: 2px
---

# Neo theme

**Parent:** [design.md](design.md) · **CSS:** `themes/neo.css` + `relief-surfaces.css` · **Selector:** `[data-theme='neo']`

Light soft UI with **relief chrome**: borderless edges, depth from dual L/S shadow stacks. Chrome is **transparent** (`--wf-chrome-fill: transparent`) so the dot grid shows through workspace, onboarding wizard, dialogs, and controls.

## Chrome mode: relief

- `--wf-chrome-mode: relief` (also `--wf-chrome-fill: transparent` on theme block)
- `--wf-border: transparent` — edges implied by shadow, not stroke
- All `--wf-chrome-border-*` → `transparent`
- `--wf-border-width: 2px` (divider/tool chrome uses white `#fff` as relief edge color)
- `--wf-divider-color: #fff`, `--wf-tool-chrome-border: #fff`
- Shared relief overrides: `components/relief-surfaces.css` (not in `neo.css`)

## Relief tuning

| Token | Value |
|-------|-------|
| `--wf-relief-shadow-rgb` | `163 163 176` |
| `--wf-relief-shadow-alpha` | `0.24` |
| `--wf-relief-highlight-rgb` | `255 255 255` |
| `--wf-relief-highlight-alpha` | `0.78` |

Primitives (`relief-primitives.css`): **L** = 4px offset / 8px blur; **S** = 3px / 6px. No spread radius.

Semantic wiring:

- Wizard / onboarding shell: inset **L** (`--wf-relief-inset-l`)
- Dialog / auth card: outset **L**
- Controls, tabs, hover: **S** outset / inset
- Flush default: `--wf-relief-flat` (no shadow)

## Palette

| Token | Value |
|-------|-------|
| `--wf-bg` | `#e0e0e6` |
| `--wf-text` | `#2a2a32` |
| `--wf-muted` | `#7a7a86` |
| `--wf-surface` / soft | `#e0e0e6` / `rgba(224,224,230,0.82)` |
| `--wf-primary` | `#3a3a44` |
| `--wf-violet` | `#7c6a9e` |
| `--wf-cyan` | `#6a8e9e` |
| `--wf-mint` | `#6a9e8a` |
| `--wf-ring` | `rgba(124, 106, 158, 0.22)` |

Status colors: `#ef4444`, `#22c55e`, `#f59e0b`.

## Canvas

**Component stack:** `AtmosphereBg` + `DotGrid` (see `canvas-layers.ts`).

| Layer | Tokens |
|-------|--------|
| Color | `--wf-bg-gradient`: `linear-gradient(145deg, #d8d8de, #e8e8ee)`; orbs violet/cyan at 6% / 5% |
| Texture | `--wf-dot-grid-tile: 10px`; `--wf-dot-grid-rgb: 42 42 50`; `--wf-dot-grid-opacity: 0.16` |
| Vignette | `--wf-overlay`: subtle top highlight + 4% bottom shade (on atmosphere only) |

Dot ink uses mask-based tiles in `canvas.css` — theme sets color/opacity only.

## Controls

- `--wf-control-border-width: 0` — no stroke on controls
- Relief fills: `--wf-chrome-fill` (transparent) via `relief-primitives.css`
- Hover/active: shadow delta only (`--wf-control-shadow-raised` = outset **S**)
- `--wf-control-border-ring-closed: #fff` (composer ring)
- DnD indicator: white 50% fill, `#fff` border

**Radius:** `--wf-radius-icon-btn: 50%` (circular icon controls).

## Onboarding & dialogs

- `.wf-onboarding-page`: `background: transparent` — same `CanvasBackground` as workspace
- `.wf-onboarding-wizard`: `--wf-shell-width` 840px × `--wf-shell-height` 540px; relief inset **L** well on transparent fill
- Step badge (current): `background: var(--wf-text)`; `color: var(--wf-bg)` for contrast

## Dialog hovers

| Variant | Background | Text |
|---------|------------|------|
| Accent | `color-mix(cyan 14%, white)` | `#0f766e` |
| Warn | `color-mix(#c2410c 12%, white)` | `#9a3412` |

## Do's and Don'ts

**Do:** Use relief **L/S** stacks for depth; keep chrome transparent so dot grid reads through; tune dot opacity via `--wf-dot-grid-opacity`.

**Don't:** Re-introduce opaque `--wf-bg` fills on panels; don't add visible border strokes; don't put vignette on `DotGrid`.
