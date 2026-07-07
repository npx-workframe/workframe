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
  shadow_color: "163, 163, 176"
  shadow_alpha: 0.9
  highlight_color: "255, 255, 255"
  highlight_alpha: 0.4
rounded:
  knob_sm: 4px
  knob_md: 4px
  knob_lg: 12px
  icon_btn: 50%
border_width: 2px
---

# Neo theme

**Parent:** [design.md](design.md) · **CSS:** `apps/web/src/styles/themes/neo.css` · **Selector:** `[data-theme='neo']`

Light soft UI with **relief chrome**: borderless edges, depth from dual light/dark shadow stacks (neo-morphic). Default raised surfaces match `--wf-bg` family (`#e0e0e6`).

## Chrome mode: relief

- `--wf-chrome-mode: relief`
- `--wf-border: transparent` — edges implied by shadow, not stroke
- All `--wf-chrome-border-*` → `transparent`
- `--wf-border-width: 2px` (divider/tool chrome uses white `#fff` as relief edge color)
- `--wf-divider-color: #fff`, `--wf-tool-chrome-border: #fff`

## Relief tuning

| Token | Value |
|-------|-------|
| `--wf-relief-shadow-color` | `163, 163, 176` |
| `--wf-relief-shadow-alpha` | `0.9` |
| `--wf-relief-highlight-color` | `255, 255, 255` |
| `--wf-relief-highlight-alpha` | `0.4` |

Composed shadows:

- `--wf-neo-flat`: 3px drop + -3px highlight
- `--wf-neo-highlight`: inverted emphasis pair
- Inset pair: `--wf-neo-shadow-inset-light` + `inset-dark`
- Controls: flush default; hover/active → `--wf-control-shadow-raised` (`--wf-neo-flat`)

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

Status colors match dark theme hex (`#ef4444`, `#22c55e`, `#f59e0b`).

## Canvas

- **Gradient:** `linear-gradient(145deg, #d8d8de, #e8e8ee)`
- **Orbs:** low-opacity violet/cyan tints (6% / 5%)
- **Grid:** 10px dark pixel tile at 2% opacity
- **Overlay:** subtle top highlight + 4% bottom shade

## Controls

- `--wf-control-border-width: 0` — no stroke on controls
- Hover/active: `--wf-control-bg-raised` + `--wf-control-shadow-raised`
- Buttons: flush → raised on hover/primary via `--wf-btn-shadow-hover/primary`
- `--wf-control-border-ring-closed: #fff` (composer ring)
- DnD indicator: white 50% fill, `#fff` border

**Radius:** `--wf-radius-icon-btn: 50%` (circular icon controls).

## Component overrides (neo-specific)

Large block in `neo.css` under `[data-theme='neo']` — patterns:

- **Shell header:** raised bg + `--wf-control-shadow-elevated`, no bottom border
- **Shell footer / theme menu:** elevated relief shadows
- **Activity tree active rows / composer expanded tools / thinking blocks:** inset or flat relief pairs
- **Tool runs (collapsed):** flat relief; expanded → inset shadows
- **Send button:** primary relief stack; disabled flattened

When adding neo styles: default **flush**, pop **raised** on interaction; never add visible `border-color` on panels.

## Dialog hovers

| Variant | Background | Text |
|---------|------------|------|
| Accent | `color-mix(cyan 14%, white)` | `#0f766e` |
| Warn | `color-mix(#c2410c 12%, white)` | `#9a3412` |

## Do's and Don'ts

**Do:** Use `--wf-neo-flat` / `--wf-control-shadow-raised` for depth; keep palette muted/desaturated.

**Don't:** Re-introduce `--wf-border` strokes on panels; don't use dark-theme glass rgba borders.
