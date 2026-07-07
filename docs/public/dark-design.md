---
version: alpha
name: Workframe — Dark theme
parent: design.md
selector: "[data-theme='dark']"
source: apps/web/src/styles/themes/dark.css
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
rounded:
  knob_sm: 4px
  knob_md: 4px
  knob_lg: 12px
  icon_btn: 4px
border_width: 1px
---

# Dark theme

**Parent:** [design.md](design.md) · **CSS:** `apps/web/src/styles/themes/dark.css` · **Selector:** `[data-theme='dark']`

Dark glass workspace with **line chrome**: visible 1px borders, flat shadows, violet/cyan ambient orbs. Neo relief tokens are present but **inert** (`--wf-neo-shadow-light/dark` → transparent).

## Chrome mode: line

- `--wf-chrome-mode: line`
- `--wf-border` / `--wf-border-strong` drive panel edges
- `--wf-chrome-border-*` scale = `color-mix` of `--wf-border` at 30%–90%
- `--wf-divider-color: rgba(255, 255, 255, 0.1)`
- `--wf-neo-flat` falls back to `--wf-shadow-md` (not dual relief)

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

- **Gradient:** multi radial (violet top-left, cyan bottom-right) + `var(--wf-bg)`
- **Orbs:** `--wf-orb-primary` violet ~0.18 opacity; `--wf-orb-secondary` cyan ~0.15
- **Grid:** 10px pixel SVG tile, white 5% opacity; mask fade `--wf-grid-mask`
- **Overlay:** light top wash + bottom vignette

## Controls & borders

**Glass control chrome** (theme block defaults):

- Border: `rgba(255, 255, 255, 0.1)`; inactive `0.05`
- Hover/active fill: `rgba(255, 255, 255, 0.1)`
- `--wf-control-shadow-*` use flat `--wf-shadow-md` / inset, not neo stacks
- `--wf-btn-border-width: 1px` with same glass border pattern
- Scrollbar thumb: `color-mix(muted 32%, transparent)` — brighter than divider alone

**Radius:** knobs 4/4/12px; `--wf-radius-icon-btn: 4px` (square controls, not circles).

## Component overrides (dark-specific)

From `dark.css` selectors — apply only under `[data-theme='dark']`:

- Panel icon controls (`.wf-panel__control-btn`, rail section actions, browser tab close): **no border, no shadow**; hover → `rgba(255,255,255,0.1)` fill
- `.wf-tool-run`, `.wf-activity-tree__row--child`: `1px solid var(--wf-tool-chrome-border)` (`rgba(255,255,255,0.05)`)
- `.wf-theme-switcher__menu`: surface fill + `--wf-chrome-border-strong` + `--wf-shadow-lg`
- Theme switcher trigger: glass border default; hover fill like other controls

## Shadows

```text
--wf-shadow-sm:  0 1px 2px rgba(0,0,0,0.06)
--wf-shadow-md:  0 4px 12px rgba(0,0,0,0.10)
--wf-shadow-lg:  0 8px 24px rgba(0,0,0,0.14)
--wf-shadow-xl:  0 20px 60px rgba(0,0,0,0.18)
--wf-shadow-inset: inset 0 1px 0 rgba(255,255,255,0.055)
```

## Do's and Don'ts

**Do:** Use border + subtle glass hover for interactive chrome; keep orbs restrained.

**Don't:** Apply neo dual-shadow stacks or 2px relief borders — they belong to neo/blueprint only.
