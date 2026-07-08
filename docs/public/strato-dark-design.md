---
version: alpha
name: Workframe — Strato Dark theme
parent: design.md
selector: "[data-theme='strato-dark']"
source: apps/web/src/styles/themes/strato-dark.css
color-scheme: dark
chrome_mode: line
colors:
  bg: "#0a0a0f"
  text: "#e8e8ee"
  muted: "#727280"
  border: "rgba(255, 255, 255, 0.07)"
  border_strong: "rgba(255, 255, 255, 0.11)"
  surface: "rgba(18, 18, 26, 0.58)"
  surface_soft: "rgba(18, 18, 26, 0.38)"
  primary: "rgba(255, 255, 255, 0.9)"
  primary_foreground: "#0a0a0f"
  violet: "#6d28d9"
  violet_glow: "#7c3aed"
  cyan: "#0e7490"
  mint: "#047857"
  ring: "rgba(109, 40, 217, 0.38)"
  error: "#ef4444"
  success: "#22c55e"
  warning: "#f59e0b"
dot_grid:
  tile: 10px
  rgb: "255 255 255"
  opacity: 0.08
rounded:
  knob_sm: 4px
  knob_md: 4px
  knob_lg: 12px
  icon_btn: 4px
border_width: 1px
---

# Strato Dark theme

**Parent:** [design.md](design.md) · **CSS:** `themes/strato-dark.css` · **Selector:** `[data-theme='strato-dark']`

Dark glass workspace with **line chrome**: visible 1px borders, flat shadows, violet/cyan ambient orbs. Uses the same `DotGrid` texture component as Neo Light; panels paint `--wf-chrome-fill: var(--wf-surface)` (semi-transparent glass) over the grid.

## Chrome mode: line

- `--wf-chrome-mode: line`
- `--wf-chrome-fill: var(--wf-surface)` — glass panels over texture
- `--wf-border` / `--wf-border-strong` drive panel edges
- `--wf-chrome-border-*` scale = `color-mix` of `--wf-border` at 30%–90%
- `--wf-divider-color: rgba(255, 255, 255, 0.1)`
- Relief primitives map to flat `--wf-shadow-*` (Neo relief stacks inert in line mode)

## Palette

| Token | Value |
|-------|-------|
| `--wf-bg` | `#0a0a0f` |
| `--wf-text` | `#e8e8ee` |
| `--wf-muted` | `#727280` |
| `--wf-border` | `rgba(255, 255, 255, 0.07)` |
| `--wf-border-strong` | `rgba(255, 255, 255, 0.11)` |
| `--wf-surface` | `rgba(18, 18, 26, 0.58)` |
| `--wf-surface-soft` | `rgba(18, 18, 26, 0.38)` |
| `--wf-primary` | `rgba(255, 255, 255, 0.9)` |
| `--wf-primary-foreground` | `#0a0a0f` |
| `--wf-violet` | `#6d28d9` |
| `--wf-violet-glow` | `#7c3aed` |
| `--wf-cyan` | `#0e7490` |
| `--wf-mint` | `#047857` |
| `--wf-ring` | `rgba(109, 40, 217, 0.38)` |

Status: `--wf-error` `#ef4444`, `--wf-success` `#22c55e`, `--wf-warning` `#f59e0b`.

## Canvas

**Component stack:** `AtmosphereBg` + `DotGrid` (see `canvas-layers.ts`).

| Layer | Tokens |
|-------|--------|
| Color | Multi radial violet/cyan gradients + `var(--wf-bg)`; orbs violet ~0.18 / cyan ~0.15 |
| Texture | `--wf-dot-grid-tile: 10px`; `--wf-dot-grid-rgb: 255 255 255`; `--wf-dot-grid-opacity: 0.08` |
| Vignette | `--wf-overlay` on atmosphere (light top wash + bottom vignette) |

Dot grid uses mask-based tiles in `canvas.css` — no separate vignette mask on the dot layer.

## Controls & borders

**Glass control chrome** (theme block defaults):

- Border: `rgba(255, 255, 255, 0.1)`; inactive `0.05`
- Hover/active fill: `rgba(255, 255, 255, 0.1)`
- `--wf-control-shadow-*` use flat `--wf-shadow-md` / inset
- `--wf-btn-border-width: 1px` with same glass border pattern
- Scrollbar thumb: `color-mix(muted 32%, transparent)`

**Radius:** knobs 4/4/12px; `--wf-radius-icon-btn: 4px` (square controls, not circles).

## Component overrides (Strato Dark-specific)

From `strato-dark.css` selectors — apply only under `[data-theme='strato-dark']`:

- Panel icon controls: **no border, no shadow**; hover → `rgba(255,255,255,0.1)` fill
- `.wf-tool-run`, `.wf-activity-tree__row--child`: `1px solid var(--wf-tool-chrome-border)`
- `.wf-theme-switcher__menu`: surface fill + `--wf-chrome-border-strong` + `--wf-shadow-lg`

## Shadows

```text
--wf-shadow-sm:  0 1px 2px rgba(0,0,0,0.06)
--wf-shadow-md:  0 4px 12px rgba(0,0,0,0.10)
--wf-shadow-lg:  0 8px 24px rgba(0,0,0,0.14)
--wf-shadow-xl:  0 20px 60px rgba(0,0,0,0.18)
--wf-shadow-inset: inset 0 1px 0 rgba(255,255,255,0.055)
```

## Do's and Don'ts

**Do:** Use border + subtle glass hover for interactive chrome; keep orbs restrained; tune dot visibility via `--wf-dot-grid-opacity`.

**Don't:** Apply Neo dual-shadow stacks or 2px relief borders; don't put vignette masks on `DotGrid`.
