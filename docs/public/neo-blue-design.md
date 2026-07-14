---
version: alpha
name: Workframe — Neo Blue theme
parent: design.md
selector: "[data-theme='neo-blue']"
source: apps/web/src/styles/themes/neo-blue.css
color-scheme: light
chrome_mode: relief
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
  shadow_rgb: "15 36 66"
  shadow_alpha: 0.82
  highlight_rgb: "255 255 255"
  highlight_alpha: 0.10
moleskine:
  tile: 24px
  line: "rgba(255, 255, 255, 0.06)"
rounded:
  knob_sm: 4px
  knob_md: 4px
  knob_lg: 12px
  icon_btn: 50%
border_width: 2px
---

# Neo Blue theme

**last_verified:** 2026-07-12

**Parent:** [design.md](design.md) · **CSS:** `themes/neo-blue.css` + `relief-surfaces.css` + `canvas.css` · **Selector:** `[data-theme='neo-blue']`

Engineering blue on deep navy: white typography, solid `--wf-bg` relief surfaces, and relief shadows with **low highlight alpha** (0.10). Canvas is a flat solid background; atmosphere effects and the moleskine grid are not mounted in relief mode.

## Chrome mode: relief

- `--wf-chrome-mode: relief`
- `--wf-chrome-fill: var(--wf-bg)` (set in `relief-primitives.css` for all relief themes)
- Relief tuning: dark blue shadow (`15 36 66` @ 0.82), white highlight @ 0.10
- `--wf-border: transparent`; all `--wf-chrome-border-*` transparent
- Shared chrome rules: `relief-surfaces.css` (theme file is palette + canvas tokens only)

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

**Status colors** remapped to white family: `--wf-error` `#ffffff`, `--wf-success` `#ffffff`, `--wf-warning` `rgba(255,255,255,0.8)`.

## Canvas

**Component stack:** `AtmosphereBg` only (`getThemeCanvasTexture` returns `null` for Neo Blue).

| Layer | Tokens |
|-------|--------|
| Color | `--wf-bg-gradient: none`; `--wf-bg: var(--wf-blue)` |
| Texture | *(not mounted)* — moleskine tokens below reserved if re-enabled: `--wf-moleskine-grid-tile: 24px`; `--wf-moleskine-grid-line: rgba(255,255,255,0.06)` |
| Atmosphere | `--wf-overlay: none`; orbs are transparent and hidden by relief-mode CSS |

## Relief stacks

Same **L/S** geometry as Neo Light (`relief-primitives.css`); Neo Blue differs only in shadow/highlight RGB and alpha. Depth is shadow-only over solid `--wf-bg` chrome surfaces.

## shadcn bridge

Neo Blue sets shadcn vars on `[data-theme='neo-blue']`:

```text
--background / --foreground → --wf-bg / --wf-text
--card, --popover → --wf-chrome-fill (transparent in relief)
--destructive → #ffffff on --wf-blue foreground
```

## Controls & accents

Follows shared relief patterns in `relief-surfaces.css`. Neo Blue-specific accents in `neo-blue.css`:

- Close buttons: `color-mix(white 22%, transparent)` hover
- Composer stop / error borders: white mixes

**Divider / tool chrome:** `#fff` at 2px logical border width (relief edge color, not rgba border).

## Do's and Don'ts

**Do:** Preserve solid `--wf-bg` chrome and relief depth. Use white copy.

**Don't:** Remove solid relief fills. Don't use saturated status reds/greens — theme uses white status glyphs.
