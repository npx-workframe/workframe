---
version: alpha
name: Workframe UI
description: Workframe layout and behavior composed with the Architectonic design-system.
source_truth:
  - apps/web/src/styles/architectonic/
  - apps/web/src/generated/architectonicThemes.ts
  - apps/web/src/styles/tokens/
  - apps/web/src/styles/components/
  - scripts/workframe/sync-architectonic-design-system.mjs
---

# Workframe UI design system

**Last verified:** 2026-07-22

Workframe keeps its dense workspace layout, Dockview topology, panel gutters, scrolling rules, and product-specific compositions. Architectonic is the canonical source for visual identity: palettes, font roles, radii, elevation, style axes, and themed backgrounds.

## Ownership boundary

| Concern | Owner | Source |
|---|---|---|
| Space, density, type scale, motion, radius geometry | Architectonic | `generated/globals.css` |
| Palette and component role tokens | Architectonic | `generated/themes/*.css` |
| Lines, shadows, and glass surface grammar | Architectonic | `generated/relief.css` |
| Docking, rails, panels, message layout, navigator, browser | Workframe | `styles/components/*.css` |
| Compatibility aliases | Workframe | `styles/architectonic/bridge.css` |
| Theme selection and persistence | Generated registry + authenticated user profile | `generated/architectonicThemes.ts`, `lib/theme.ts`, `services/workframe-api/user_prefs.py` |

Component CSS must consume semantic roles. It must not branch on a concrete theme name. A new theme should normally require only an Architectonic theme definition and manifest entry.

## Deterministic synchronization

Run from the Workframe root:

```powershell
npm.cmd run sync:design-system
```

The sync command reads `../architectonic/design-system` by default, or `ARCHITECTONIC_DESIGN_SYSTEM_DIR` when supplied. It vendors:

- structural globals;
- the lines/shadows/glass style axis;
- every theme stylesheet;
- the machine-readable manifest;
- a generated TypeScript registry;
- the pre-paint theme bootstrap embedded in `apps/web/index.html`.

The snapshot records the Architectonic package version and a SHA-256 source hash. Workframe builds can use the committed snapshot when the sibling repository is absent, so CI, Docker, npm scaffolds, and the desktop bundle remain standalone and reproducible.

Never hand-edit files under `styles/architectonic/generated/` or `src/generated/architectonicThemes.ts`.

## Runtime axes

`applyTheme()` sets these independent attributes on `<html>`:

| Attribute | Values | Meaning |
|---|---|---|
| `data-arch-theme` | registry theme id | identity |
| `data-color-mode` | `light`, `dark` | contrast and native color scheme |
| `data-style` | `lines`, `shadows`, `glass` | surface separation |
| `data-texture` | registry texture id | canvas recipe |
| `data-density` | `technical` | Workframe's compact app density |
| `data-space` | `default` | structural spacing scale |
| `data-type-scale` | `compact` | dense workspace typography |
| `data-chrome-mode` | `line`, `relief`, `glass` | Workframe compatibility axis |

`data-theme` mirrors the canonical theme id for persistence and DOM observation; component CSS should prefer the semantic axes above.

## Available themes

The registry currently exposes 18 themes:

- Lines: Mono, Minimal Light, Minimal Dark, Minimal Color
- Neo: Neo Light, Neo Dark, Neo Color
- Brutalist: Brutalist Light, Brutalist Dark
- Glass: Liquid Glass Light/Dark, Frosted Glass Light/Dark
- Specialized: Bauhaus, Leather Book, Newspaper, Notebook, Blueprint

Legacy stored values migrate once: `strato-dark` becomes `liquid-glass-dark`, and `neo-blue` becomes `neo-dark`. `dark`, `light`, and `neo` use the aliases from Architectonic's manifest.

Each registry entry also owns a four-role preview palette (`canvas`, `surface`, `ink`, and `accent`). The shared theme grid uses that metadata in both User Settings → Appearance and the early admin/invitee onboarding step, so preview cards cannot drift from the source package. A confirmed selection is stored on the authenticated user profile and restored after sign-in; local storage remains the pre-sign-in paint cache.

## Workframe semantic bridge

Workframe components continue to read stable `--wf-*` roles. The bridge maps Architectonic roles such as:

| Architectonic | Workframe |
|---|---|
| `--bg`, `--surface*` | `--wf-bg`, `--wf-surface*` |
| `--fg`, `--fg-muted` | `--wf-text`, `--wf-muted` |
| `--line*` | `--wf-border*`, chrome border scale |
| `--primary`, `--ring` | `--wf-primary`, `--wf-ring` |
| `--ok`, `--warn`, `--bad`, `--info` | Workframe status and notice roles |
| `--field-*` | shared Input/Textarea/Checkbox primitives |
| `--shadow-*`, `--neu-*` | Workframe line/relief surface primitives |
| `--theme-canvas-*` | the fixed Workframe canvas texture layer |

The bridge also supplies shadcn/Tailwind color variables so Radix/shadcn primitives use the same source of truth.

## Component rules

- Prefer the existing primitives: `Input`, `Textarea`, `Checkbox`, `Button`, `WfActionButton`, `Dialog`, `ScrollArea`, and panel primitives.
- Put behavior and accessibility in React; put visual state in semantic CSS classes.
- Keep one scroll owner per surface. Popovers may scroll internally; panels must not nest full-height scroll containers.
- Preserve the 4px Workframe layout grid and technical density unless a product requirement changes them.
- Use `--wf-*`, Architectonic role tokens, or structural `--ar-*` tokens. Do not add a component-specific theme-name selector.
- Pill geometry is semantic, not inherited: only compact labelled buttons and single-line inputs up to 40px may use `--wf-radius-compact-control`. Rows, tabs, cards, multiline inputs, dialog and wizard surfaces cap at 8px; square icon controls use 4px. Panel-header controls are circular, stay visually flush at rest, and reveal their border/shadow only on hover or focus. Compact pill buttons receive half-height inline padding. Avatars and intentional circular indicators are exempt.
- Relief uses high/low shadow state, not color changes. Line themes use borders. Glass uses translucent surfaces and blur.
- Theme backgrounds belong to `--theme-canvas-*` and `CanvasBackground`, not individual panels.

## Verification

For any design-system change:

1. Run Architectonic `npm.cmd test`.
2. Run Workframe `npm.cmd run sync:design-system` and the web build.
3. Check at least one lines, shadows, glass, and specialized theme.
4. Check workspace, auth, onboarding, settings, dialog, composer, navigator, browser, and activity surfaces.
5. Verify selection persists after reload and the initial document attributes match before React mounts.
6. Build the desktop shell after any theme asset or bootstrap change.
7. Verify the packaged `index.html` carries the `workframe-build.json` asset revision on entry CSS and JavaScript URLs so Docker upgrades cannot reuse stale immutable assets.

Use `/dev/theme` for token inspection, then verify real product surfaces; the showcase is not a substitute for Workframe visual regression.
