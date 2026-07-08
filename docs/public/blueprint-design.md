---
version: alpha
name: Workframe — Blueprint theme
parent: design.md
selector: "[data-theme='blueprint']"
source: apps/web/src/styles/themes/blueprint.css
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

# Blueprint theme

**Parent:** [design.md](design.md) · **CSS:** `themes/blueprint.css` + `relief-surfaces.css` + `canvas.css` · **Selector:** `[data-theme='blueprint']`

Engineering blueprint on deep blue: white typography, relief shadows with **low highlight alpha** (0.10), and **transparent chrome** (`--wf-chrome-fill: transparent` via relief mode) so the moleskine grid shows through workspace, onboarding, and all relief surfaces.

## Chrome mode: relief

- `--wf-chrome-mode: relief`
- `--wf-chrome-fill: transparent` (set in `relief-primitives.css` for all relief themes)
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

## Canvas & moleskine grid

**Component stack:** `AtmosphereBg` + `MoleskineGrid` (see `canvas-layers.ts`).

| Layer | Tokens |
|-------|--------|
| Color | Flat `linear-gradient(145deg, var(--wf-blue), var(--wf-blue))`; white orbs ~6% / 5% |
| Texture | `--wf-moleskine-grid-tile: 24px`; `--wf-moleskine-grid-line: rgba(255,255,255,0.06)` |
| Vignette | `--wf-overlay` on atmosphere (not on grid) |

`MoleskineGrid.tsx` + `canvas.css`: repeating 1px horizontal + vertical lines on 24px spacing. Texture is viewport-fixed — same grid on onboarding and workspace.

## Relief stacks

Same **L/S** geometry as neo (`relief-primitives.css`); blueprint differs only in shadow/highlight RGB and alpha. Depth is shadow-only on transparent chrome — no opaque surface re-paint.

## shadcn bridge

Blueprint sets shadcn vars on `[data-theme='blueprint']`:

```text
--background / --foreground → --wf-bg / --wf-text
--card, --popover → --wf-chrome-fill (transparent in relief)
--destructive → #ffffff on --wf-blue foreground
```

## Controls & accents

Follows shared relief patterns in `relief-surfaces.css`. Blueprint-specific accents in `blueprint.css`:

- Close buttons: `color-mix(white 22%, transparent)` hover
- Composer stop / error borders: white mixes

**Divider / tool chrome:** `#fff` at 2px logical border width (relief edge color, not rgba border).

## Do's and Don'ts

**Do:** Preserve grid visibility everywhere (transparent chrome). Use white copy and restrained grid lines.

**Don't:** Paint opaque fills over chrome surfaces. Don't use saturated status reds/greens — theme uses white status glyphs. Don't duplicate moleskine on `.wf-workspace-shell` — texture is canvas-only.
