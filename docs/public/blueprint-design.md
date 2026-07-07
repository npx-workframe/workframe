---
version: alpha
name: Workframe — Blueprint theme
parent: design.md
selector: "[data-theme='blueprint']"
source: apps/web/src/styles/themes/blueprint.css
color-scheme: light
chrome_mode: relief
workspace_chrome_fill: transparent
colors:
  bg: "#1a3658"
  blue_deep: "#0f2442"
  text: "#ffffff"
  muted: "rgba(255, 255, 255, 0.6)"
  border: transparent
  border_strong: "rgba(255, 255, 255, 0.2)"
  surface: "#1a3658"
  violet: "#1a3658"
  cyan: "#ffffff"
  mint: "rgba(255, 255, 255, 0.75)"
  ring: "rgba(255, 255, 255, 0.35)"
relief:
  shadow_color: "15, 36, 66"
  shadow_alpha: 0.9
  highlight_color: "255, 255, 255"
  highlight_alpha: 0.1
rounded:
  knob_sm: 4px
  knob_md: 4px
  knob_lg: 12px
  icon_btn: 50%
border_width: 2px
grid_tile: 24px
---

# Blueprint theme

**Parent:** [design.md](design.md) · **CSS:** `apps/web/src/styles/themes/blueprint.css` + `components/canvas.css` · **Selector:** `[data-theme='blueprint']`

Engineering blueprint on deep blue: white typography, relief shadows with **low highlight alpha** (0.1), and **transparent workspace chrome** so the moleskine grid shows through panels.

## Chrome mode: relief + transparent workspace

- `--wf-chrome-mode: relief` (same shadow math as neo)
- `--wf-workspace-chrome-fill: transparent` — workspace panels do not paint opaque surface over grid
- Relief tuning uses dark blue shadow (`15, 36, 66`) and subtle white highlight (10%)
- `--wf-border: transparent`; chrome borders all transparent (relief only)

## Palette

| Token | Value |
|-------|-------|
| `--wf-blue` | `#1a3658` |
| `--wf-blue-deep` | `#0f2442` |
| `--wf-bg` | `var(--wf-blue)` |
| `--wf-text` | `#ffffff` |
| `--wf-muted` | `rgba(255, 255, 255, 0.6)` |
| `--wf-border-strong` | `rgba(255, 255, 255, 0.2)` |
| `--wf-surface` / soft | `var(--wf-blue)` |
| `--wf-primary` | `var(--wf-blue)` |
| `--wf-primary-foreground` | `#ffffff` |
| `--wf-violet` | `var(--wf-blue)` (accent remapped) |
| `--wf-violet-glow` | `#ffffff` |
| `--wf-cyan` | `#ffffff` |
| `--wf-mint` | `rgba(255, 255, 255, 0.75)` |
| `--wf-ring` | `rgba(255, 255, 255, 0.35)` |

**Status colors** remapped to white family: `--wf-error` `#ffffff`, `--wf-success` `#ffffff`, `--wf-warning` `rgba(255,255,255,0.8)`, `--wf-danger` → `--wf-error-soft`.

## Canvas & moleskine grid

- **Gradient:** flat `linear-gradient(145deg, var(--wf-blue), var(--wf-blue))`
- **Orbs:** white at ~6% / 5% opacity
- **Grid tile:** `--wf-grid-tile: 24px`
- **Grid line:** `--wf-grid-line: rgba(255, 255, 255, 0.05)`
- **Pixel grid image:** `none` — blueprint uses **CSS line grid** instead

`canvas.css` applies moleskine to:

- `[data-theme='blueprint'] .wf-canvas__grid`
- `[data-theme='blueprint'] .wf-workspace-shell`

Repeating 1px lines on 24px spacing; no mask fade.

## Relief stacks

Same structure as neo (`--wf-neo-flat`, inset pairs, `--wf-control-shadow-elevated`) but with blueprint relief RGB values. Shadows use `rgba(15, 36, 66, …)` in `--wf-shadow-sm` … `xl`.

## shadcn bridge

Blueprint sets shadcn/Tailwind semantic vars on `[data-theme='blueprint']`:

```text
--background / --foreground → --wf-bg / --wf-text
--card, --popover → --wf-surface
--destructive → #ffffff on --wf-blue foreground
--shadow-* → neo relief stacks
```

Use when styling shadcn primitives inside blueprint only.

## Controls & component overrides

Follows neo relief patterns (flush → raised on hover) with blueprint-specific selectors for:

- Shell header/actions/footer (white mono brand treatment on `.wf-brand-img--mono`)
- Activity tree active / composer expanded / thinking / tool-run states (white-on-blue relief)
- Send button: white fill, blue text when active

**Divider / tool chrome:** `#fff` at 2px logical border width (relief edge color, not rgba border).

## Do's and Don'ts

**Do:** Preserve grid visibility in workspace panels (`transparent` chrome fill). Use white copy and restrained grid lines.

**Don't:** Paint opaque `--wf-surface` over workspace shell (breaks blueprint metaphor). Don't use saturated status reds/greens — theme uses white status glyphs.
