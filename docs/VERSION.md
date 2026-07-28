# Workframe v0.1.29

| Component | Version |
|-----------|---------|
| create-workframe | 0.1.29 |
| workframe CLI (`npx workframe`) | 0.2.2 |
| Workframe API / UI | 0.1.29 (bundled in create-workframe) |

```bash
npx create-workframe@0.1.29 MyProject
npx workframe@0.2.2
```

Hermes gateway image: `nousresearch/hermes-agent:latest` (updated via stack admin).

## 0.1.29

- Fix install wizard **invalid host** on public domains: `POST /api/install/register-admin` now bypasses SECURE_MODE host validation during the install window.

## 0.1.28

- Branding: `workframe-color` SVG mark, generated favicon/PWA/OG assets, SEO metadata on web + website (`site_meta.py` defaults).
- Onboarding wizard high relief on neo themes (reuses `--wf-relief-outset-l`, same as dialog).
- Compact theme picker 2-column grid in install wizard.
- Inactive disabled wizard CTAs use `--wf-btn-fg-inactive` without whole-element opacity fade.
- ABX visual QA audit, theme-smoke checklist, and Playwright harness scripts.

## 0.1.26

- Mobile workspace layout: responsive Dockview, settings sheet tabs, inner-page gutters, iPhone standalone PWA hooks.
- Panel header chrome normalization, compact pill controls, message navigator polish.
- Bridge and foundation token tweaks for mobile breakpoints.

## 0.1.25

- Bauhaus Mondrian theme: unified ink/paper anchors (`#111111` / `#eeeeee`), panel accent fields, centered chat column, black composer shell, and Mondrian browser/rail/files/activity chrome.
- Sync Architectonic design-system structural contrast scale, Bauhaus RGB relief tokens, and manifest preview alignment.
- Brutalist shared chrome layer; bridge aliases theme palette without hex drift in product CSS.

## 0.1.24

- Unify control/surface tokens: floating vs modal split, icon controls, elevated surfaces across composer, dialogs, toasts, tooltips, and browser chrome.
- Cap large container radius at 8px; keep pills, rail items, and circular controls intentionally round.
- Sync Architectonic design-system 0.4.1 (floating/modal surface tokens, surface radius cap).
- Stack updates panel progress helper and message-nav theme tokens.

## 0.1.23

- Blueprint and Notebook square line chrome: opaque grid-mask fills, border-only hover, square scrollbar thumbs.
- Theme picker: page-adapted card contour, faithful per-theme previews from Architectonic manifest, checkmark-only selection.
- Sync Architectonic chrome tokens (`chrome-fill`, theme swatch pattern) and generated preview map.
- Settings dialog relief clip fix, rail nav label alignment, and assorted neo/relief chrome polish.

### workframe CLI 0.2.2

- Align package README and `docs/VERSION.md` with the published `0.2.x` local-link console (read-only discovery + optional consent-gated provider test).
- Point installers to create-workframe 0.1.24 for the full product cell.

## 0.1.22

- Fix neo-light scrollbar thumb color via per-theme tokens (restore solid white thumb; remove architectonic bridge blanket override).
- Collapse navigator and activity panels by default; clear solo-panel max-width so single panels fill the workspace.
- Refine neo relief chrome: high-relief active rail items, circular attach/send controls, 4px browser tab radius, pointer cursors, and shadow-only interactive depth without white border rings.
- Improve browser toolbar active-mode relief, tab chrome, navigator controls, and file-tree selection affordances.

## 0.1.21

- Converge settings, authentication, onboarding, and wizard surfaces on the shared design-system field, action, switch, avatar, and Neo relief contracts.
- Restore Neo Dockview boundaries and browser-tab relief while keeping panel chrome quiet, compact, and consistent across light and dark themes.
- Normalize settings gutters, rail titles, 32px fields, button contrast, profile avatars, and hover-only circular icon-control borders.
- Replace the remaining workspace-specific Architectonic source pointer with a portable repository-relative reference.

## 0.1.20

- Make agent-owned model selection, provider credential resolution, fallbacks, Codex authentication, and persisted provider/model attribution consistent across onboarding, settings, DMs, and rooms.
- Add recursive Navigator selection/download archives, safe batch deletion, bounded filenames, and in-browser image, audio, video, PDF, and CSV previews.
- Add persistent reactions, compact replies, avatar-backed mentions, upload routing, rich attachment rendering, and a smooth message navigator without competing with the chat scrollbar.
- Reconcile Thinking/tool disclosures, Markdown artifacts, panel headers, borders, and scrollbars with the existing neumorphic theme system.
- Align settings and onboarding with shared Architectonic switches and Workframe action roles; restore Neo Dockview boundaries, browser-tab relief, 32px fields, quiet circular icon controls, and profile avatars.

## 0.1.19

- Use the ChatGPT-account-supported `gpt-5.4-mini` Codex default and remove unsupported direct-API models from the Codex picker.
- Migrate existing generated Codex profiles before chat resolves its model, preventing one stale `gpt-5.4-medium` dispatch.

## 0.1.18

Release candidate: updater-path repair and Neo auth action/OTP refinements.

## 0.1.17

- Select the host-bindings compose overlay for Windows host paths during Hermes updates, even when the supervisor cannot see the host path inside its Linux container.

## 0.1.16

- Mount the installed project root into the API container so in-app updates can resolve `workframe-manifest.json`.

## 0.1.15

- Shared project-room sessions across users with per-turn invitee credential overlays; DMs remain private per-user proxy sessions.
- Canonical room message IDs replace optimistic client IDs to prevent duplicated room messages.

## 0.1.14

- UI theme rebrand: `strato-dark`, `neo-light`, `neo-blue` (legacy slug migration); relief/line chrome tokens and onboarding polish.
- Onboarding wizard: `agent_model` step + CopyInput on public URL step (aligned with backend flow).

## 0.1.13

- Gate-run A–D: server.py split to ~2.6k lines + handler_modules; WF-012 build stamp; WF-016 receipt per run; WF-036 ConciergeFlow/HermesSession decompositions.
- Public repo verify: remove operator-specific paths from tracked docs/tests.

## 0.1.12

- Chat wait hints gated on active turns; fix group-room live SSE stale snapshots and batcher flush.
- Project room message cache (stale-while-revalidate) matching DM bind pattern.
- Public deploy verify: anonymous `/api/snapshot` must return 401.

## 0.1.11

- Sync all install scripts from npm pack during in-app Workframe apply.

## 0.1.10

- Defer supervisor self-restart during in-app Workframe apply (SECURE_MODE).

## 0.1.9

- Fix in-app Workframe apply on SECURE_MODE: API prefetches npm, supervisor rebuilds (control-net has no registry egress).
- Fix compose apply from supervisor on Windows (skip host-bindings when host path is not visible in-container).
- Record installed pack version in `workframe-api/data/package-version` after apply.
