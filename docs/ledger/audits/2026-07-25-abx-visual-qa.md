# ABX visual QA audit — 2026-07-25

**Campaign:** WF-UI-004 / WF-UI-005 / WF-UI-006  
**Install:** `npx create-workframe@0.1.26 ABX` at `http://127.0.0.1:18644`  
**Scope:** UI/CSS/tokens only — no LLM chat, no backend changes.

## Themes

**Registry:** 18 synced from Architectonic (`architectonicThemes.ts`).  
**Visible in picker:** 14 — filtered by `HIDDEN_THEME_PICKER_IDS` in `themeOptions.ts`.

Hidden (valid if already selected, not shown in switcher/settings grid):
`mono`, `neo-color`, `minimal-color`, `leather-book`

**Test matrix (visible only):**

| Family | Themes |
|--------|--------|
| Lines | minimal-light, minimal-dark |
| Neo | neo-light, neo-dark |
| Brutalist | brutalist-light, brutalist-dark |
| Glass | liquid-glass-light, liquid-glass-dark, frosted-glass-light, frosted-glass-dark |
| Custom | bauhaus, newspaper, notebook, blueprint |

Do not spend QA cycles on hidden themes unless a regression is reported for a legacy persisted preference.

## Breakpoints

- Desktop: ≥1280px
- Mobile: 390×844 (iPhone standalone PWA layout hooks)

## Screen matrix

| Surface | Desktop | Mobile | Notes |
|---------|---------|--------|-------|
| Install window | | | |
| Auth OTP | | | |
| Wizard (all steps) | | | |
| Shell / Dockview | | | |
| Chat / composer | | | |
| Files / Browser / Activity | | | |
| Settings (profile, connect, agents, appearance, updates) | | | |
| Modals / dialogs | | | |
| Provider / model pickers | | | |

## Findings

_(populated during Phase 3–4)_

## Fix rounds

_(commit refs per round)_
