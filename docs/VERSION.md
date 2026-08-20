# Workframe v0.1.61

| Component | Version |
|-----------|---------|
| create-workframe | 0.1.61 |
| workframe API / UI | 0.1.61 (bundled in create-workframe) |
| workframe CLI (`npx workframe`) | 0.2.2 |

```bash
npx create-workframe@0.1.61 MyProject
npx workframe@0.2.2
```

Hermes gateway image: `nousresearch/hermes-agent:latest` (updated via stack admin).

## 0.1.61

- Prefer the canonical supervisor-aware updater when older root-level script wrappers remain mounted.

## 0.1.60

- Count vault-backed workspace LLM credentials as available to the model picker.

## 0.1.59

- Fixed credential lifecycle activation so saved provider bindings remain active and immediately available to the model picker.

## 0.1.58

- Claim the verified install admin as the default workspace owner and active owner membership during setup resume.

## 0.1.57

- Resume an install with an existing owner through the visible owner-auth gate when a setup mutation returns forbidden.

## 0.1.56

- Prefer the configured stack supervisor for in-app updates when Docker is also exposed to the API, avoiding read-only compose mounts that can fail after release download.

## 0.1.55

- Harden in-app UI updates with staged entry-asset closure validation so a partial tree cannot blank the app.
- Make user provider saves durable before runtime bootstrap so gateway health work cannot make a successful key save appear to fail.
- Distinguish Discord and Telegram bot-token labels for accessible workspace integration forms.

## 0.1.54

- Release the next npm package version through the trusted GitHub Actions publish workflow.

## 0.1.52

- Add clean, permissioned shared-room history reset with synchronized UI, API, and Hermes session boundaries.

## 0.1.51

- Reload Workframe after an in-app update with a unique URL so stale index HTML cannot survive the restart.
- Sync the canonical Nginx config through source, package, generated installs, and existing-install updates.
- Gate generated installs on no-store index HTML while retaining immutable hashed assets.

## 0.1.50

- Preserve the API-resolved host compose and project roots across the deferred supervisor restart, overriding stale install `.env` values.
- Resolve supervisor updater scripts from the canonical install tree when a stale script bind mount is empty, keeping both Workframe and Hermes updates operable.
- Extend the updater release gate to cover host-root forwarding and supervisor script fallback.

## 0.1.49

- Restore the profile settings Save action to the theme-aware settings footer; remove the legacy filled body button introduced in 0.1.33.
- CI and trusted npm publishing now fail if profile settings regress from the footer/neo action contract.
- Post-update Docker cleanup is bounded and non-fatal, so a slow daemon cannot leave a completed update permanently “in progress.”
- Deferred supervisor reboot uses a container-native bind target, so the same updater path works on Linux hosts and Docker Desktop.

## 0.1.48

- Updater completion now requires durable supervisor job success plus version alignment across the package pin, compose environment, API, UI, and running supervisor.
- Workframe updates recover stale Created-state gateway/dashboard containers and restart the supervisor with valid Compose overlay arguments.
- Hermes updates report the installed agent version, verify image-digest convergence, and reload the Workframe UI only after the recreated services are running.

## 0.1.47

- Test release for validating the in-app updater path.

## 0.1.46

- Root cause of half-applied updates: the apply script runs inside the supervisor container, and mid-apply dependency recreation (UI `up` without `--no-deps`, early supervisor-restart sibling) could recreate the supervisor and kill the apply itself. Supervisor restart now runs as the final step; UI recreate uses `--no-deps` with gateway/dashboard explicitly started first.
- Supervisor restart sibling retries with an explicit remove if recreate leaves a Created-state container.

## 0.1.45

- Updates panel reports "Update in progress" while an async apply holds the stack lock, instead of drift + a second Update button; apply requests are rejected while one is running.
- Hermes update recreates gateway/dashboard with host-bindings overlay (fixes broken `/compose/...` binds from supervisor) and restarts nginx so cached upstream IPs refresh.

## 0.1.44

- Defer UI sync until after API rebuild; stop+rm nginx before replacing `public/` (fixes stale bind 403).
- Drop user-facing drift/repair messaging — Update is the only action.

## 0.1.43

- UI health check requires `index.html` in nginx docroot (catches 403 after stale bind mount).

## 0.1.42

- UI sync replaces `workframe-ui/public` entirely so stale hashed assets cannot survive across updates.
- Force-recreate UI nginx after public dir replace so bind mounts refresh (avoids 403).

## 0.1.41

- Acquire stack-apply lock after tarball re-exec so the same PID does not block itself.

## 0.1.40

- Stack apply lock prevents concurrent supervisor applies (docker name conflict / API stuck in Created).
- Prune Created-state compose containers before API/UI recreate; retry recreate once on failure.

## 0.1.39

- Write `package-version` pin only after running API verifies — no more false drift from partial apply.
- Updates panel: single Update action (no Repair label); neo-themed flush buttons that beat global primary styles.

## 0.1.38

- Apply update re-execs itself after tarball sync so the synced script (not the stale in-memory copy) runs recreate.
- Load `WORKFRAME_HOST_*` from install `.env` inside compose helpers when supervisor env omits them.

## 0.1.37

- Supervisor apply: recreate API/UI via `workframe_compose_recreate` (host-bindings overlay) so bind mounts resolve to real host paths, not `/compose/...` on Linux VPS.
- Resolve `WORKFRAME_HOST_*` from install `.env` when API/supervisor env omits them; public overlay no longer hardcodes host root to `/compose`.
- UI health check probes inside the nginx container; deferred supervisor restart uses host-bindings compose files.

## 0.1.36

- Apply update: commit `WORKFRAME_API_VERSION` / package pin / compose env **before** container recreate (`--force-recreate`); post-apply alignment verify fails fast on mismatch.
- Fresh installs write `WORKFRAME_API_VERSION` to `.env` at scaffold time.
- Supervisor apply restarts UI via host-bindings overlay (fixes blank page after in-app update).

## 0.1.35

- Stack updates: async supervisor apply, sibling-container supervisor restart (no self-kill), public compose overlay parity, health-check retries.
- Updates UI: actionable badge, drift repair copy, restart-tolerant apply flow, build fix in settings sheet.

## 0.1.34

- Updates panel detects install drift (package pin vs compose env vs API/UI build stamps) and offers Repair instead of false “Up to date”.
- `workframe-api-build.json` stamped at pack sync; `apply-update-workframe.sh` only bumps pin after template sync and syncs `WORKFRAME_API_VERSION` in `.env` and `docker-compose.yml`.

## 0.1.33

- LLM model prefs: members can save via `selection_only` without admin 403s; `billing_ready` on model surface.
- Credential connect returns immediately (sync bootstrap); runtime credentials refresh with `wait_healthy=True`.
- Run-authority deny messages in chat use specific `llm_error_glossary` copy per deny reason.
- Concierge onboarding wizard refactor (inlined flow); ModelPicker and profile sheet polish.

## 0.1.32

- Gateway recreate uses host-bindings overlay when `WORKFRAME_HOST_*` is set (fixes Agents mount split blocking profile API health on VPS).
- Device OAuth: human `session_not_found` copy, flush dialog styling, auto-retry; supervisor reads OAuth logs across API/gateway mount paths.
- Chat connect errors use the native agent display name; admin OAuth/Stripe onboarding polish.

## 0.1.31

- SMTP onboarding errors no longer masquerade as LLM “API key rejected”; install email test returns `smtp_*` codes with SMTP-specific hints.

## 0.1.30

- Publish wizard copy fields: transparent inner input on relief chrome (no nested inset fill).
- Public installs: `allowed_hosts()` includes `APP_BASE_URL` / stack `app_base_url` hostname (fixes theme save **invalid host** after register-admin).

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
