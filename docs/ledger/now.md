# Now — shipping wedge (v0.1.x)

**Last updated:** 2026-07-21
**Package:** `0.1.19` (see [VERSION.md](../VERSION.md))
**Active plan:** [gate-run-2026-07-08.md](handoffs/gate-run-2026-07-08.md) — close Stages A→D, stop at E

## One line

Hermes-native **multi-user Workframe cell** on Docker/VPS: invite teammates, BYOK/company-pays, vault + per-turn leases, in-app updates — not the full north-star marketplace/cell manager yet.

## Shipped (this wedge)

| Area | Status | Evidence |
|------|--------|----------|
| Docker stack (UI, API, gateway, supervisor) | shipped | `infra/compose/workframe/` |
| Multi-user auth, invites, RBAC | shipped | `services/workframe-api/` |
| Credential vault + `wf_rt_*` leases | shipped | `credential_vault.py`, `turn_credentials.py` |
| Internal LLM proxy (lease → provider) | shipped | `llm_proxy.py` |
| Model/settings unification | shipped | v0.1.8+ |
| In-app Workframe update (SECURE_MODE) | shipped | v0.1.9–0.1.11 |
| Public deploy verify script | shipped | `scripts/workframe/verify-public-deploy.sh` |
| Agent egress doctrine (docs) | shipped | [security.md](../public/security.md) |
| Harness verify (cloud/API/build/scaffold) | shipped | `.harness/verify.mjs` |
| Dogfood sign-off (MyBusiness Docker) | **done** | Alan 2026-07-05 — wizard + chat |

## Active (next proof layers)

### 2026-07-21 provider/model convergence

- The agent template now owns the primary model and fallback chain. Per-user `u-*` profiles remain credential/session isolation runtimes and synchronize the agent's model choice; they are not an independent preference surface.
- Credentials remain user-owned (BYOK/OAuth) or workspace-owned (company-pays). If the configured provider is unavailable for the acting user, the run denies with a connect-provider error instead of silently changing the agent to another provider.
- DM, room mention, settings, composer, and slash-model callers now resolve the same agent-owned model surface. Room responses persist immutable provider/model turn metadata, so changing an agent later cannot relabel historical messages.
- Provider pickers use live provider catalogs, open on the current agent provider, retain an advanced model-ID escape hatch without presenting a fake `custom` provider, and share the existing neumorphic settings shell. Settings screens reset to the top and keep one scroll owner.
- Local verification: 95 API tests; web production build; Electron build + typecheck; all five scaffold packs; package-install and negative-install evidence. The repository-wide lint command still reports the known React-hooks baseline and is not claimed as green.
- Live Docker DogFood was rebuilt with the canonical API and UI. Fresh AIbert DM and project-room turns both ran through `Codex · gpt-5.4-mini`; DM and room image attachments rendered and completed `vision_analyze`; room attribution appeared during streaming and remained immutable after reload. The live/persisted merge produced one assistant reply, with no duplicate transient row, and no silent OpenRouter reroute.

### 2026-07-21 Navigator file actions

- Navigator now has a file-and-folder selection mode built from the existing toolbar, button, checkbox, notice, scroll-area, and confirmation-dialog components. A single selected file downloads with its original filename; multiple files or selected folders download as a ZIP that recursively preserves their workspace-relative paths. Folder and child selections are deduplicated.
- Bulk deletion is authenticated and guarded by an explicit count-based confirmation. The API validates the entire selection before mutation, rejects protected, missing, folder, traversal, and out-of-workspace targets, caps actions at 500 files, and closes Browser tabs for deleted files.
- Long names now stay inside the Navigator panel with ellipsis. Selection checkboxes retain the neumorphic surface: unchecked is inset, checked is flush, with theme-correct check colors. Download feedback is the compact `Download started.` status rather than echoing a long filename.
- Browser file tabs now use authenticated raw URLs for PNG/JPG, audio, video, and PDF previews; CSV remains an authenticated text fetch rendered as a table. Binary previews no longer make the text API decode media files, and PDF owns its native scroll surface instead of nesting scroll containers.
- Verification: 101 API tests and the full web/Python/Electron production build pass. Live Docker DogFood proof covered recursive folder ZIP, selection/deletion gating, compact feedback, bounded long names, PNG/JPG/MP3/MP4/PDF/CSV rendering, exact two-file deletion, immediate Navigator refresh, deleted-tab cleanup, and a clean browser runtime log.

### 2026-07-21 chat disclosures and artifact Markdown

- Thinking segments now render through the same `ToolRunCard` disclosure used by tool calls: compact collapsed row, semantic glyph beside the chevron, and one right-edge progress/result icon with no redundant status word. The expansion behavior is identical, and the separate Thinking disclosure/CSS path was removed.
- Browser Markdown now uses a technical artifact scale aligned with the 13px chat body: 24px H1, 18px H2, and 15px H3, with tighter document spacing and wrapped code for narrow dock panels.
- Markdown structure remains shared across themes while relief identity comes from existing Workframe role tokens. Neo themes render inline code, code blocks, tables, callouts, details, quotes, and media as inset or raised surfaces; line-mode themes retain their hairline treatment.
- The implementation follows `architectonic/design-system` principles: structure/identity separation, one compact type scale, semantic surface roles, calm states, and no one-off colors or shadow recipes.
- Verification: 101 API tests and the full web/Python/Electron build pass. Docker DogFood served the same hashed source/package/install bundle; live visual proof covered collapsed and expanded Thinking cards beside tool calls plus a successful activity artifact with computed 13/24/18/15px hierarchy, wrapped code, and neo relief surfaces.

### 2026-07-21 chat message interactions and rhythm

- Thinking and tool disclosures in chat, plus tool rows in Activity, no longer draw a white outline; they retain the theme-owned neumorphic relief shadow. Message rows now use one symmetric spacing interval between each divider, header, and message body, including Markdown bodies that previously carried an extra 12px bottom pad.
- Every persisted user or agent message exposes compact reply and reaction actions built from the existing shadcn-owned button, tooltip, and dropdown components. Room replies persist the real `parent_message_id`; agent-DM replies preserve visible context as a Markdown quote. Reply previews deliberately exclude hidden reasoning.
- Reactions are authenticated and durable for room and user-namespaced DM scopes. A compact Architectonic-inspired message navigator sits beside the chat scrollbar, distinguishes user/agent markers, tracks the current row, and jumps to an accessible message label without creating a second scroll surface.
- Verification: 104 API tests and the full web/Python/Electron production build pass. Docker DogFood proof covered reply preview/cancel, exact emoji persistence across reload, cleanup, and marker navigation. A live migration-version collision with the existing run-ledger migration was caught during browser testing and fixed by assigning reactions migration 15.

### 2026-07-12 stabilization finding

- Package-install and negative-install evidence now match `0.1.18`; the release verifier fails closed on stale evidence.
- The Docker UI/API/gateway/supervisor stack is healthy after a bounded service recycle.
- Browser chat exposed the remaining blocker: the generated Codex runtime profile selects `gpt-5.4-medium`, which Codex through a ChatGPT account rejects with HTTP 400. The UI model badge can show `gpt-5.4-mini` while dispatch still reads the stale generated profile.
- Canonical source now makes `gpt-5.4-mini` the Codex MVP/default and removes the unsupported medium model from the Codex picker. Focused model-surface tests pass.
- That required proof was completed in the release-candidate result below.

### 2026-07-12 release candidate result

- `create-workframe@0.1.19` is the current candidate; version agreement passes.
- Canonical API, installer mirror, packed artifact, and non-destructive MyBusiness dogfood preview contain the Codex profile migration fix.
- Authenticated browser proof passed: `WORKFRAME_OK — ABX` from `gpt-5.4-mini`; refresh also showed the composer on `gpt-5.4-mini`.
- Package-install, negative-install, and FirstRunEvidence all allow at `0.1.19`; `verify-release-gates.mjs` allows all tracked gates.
- Public-repository verification passes. npm publication has **not** occurred because `npm whoami` returns `401 Unauthorized`.
- **Next action:** authenticate npm as the package owner, rerun `npm whoami`, publish 0.1.19, then update and verify the three VPS cells through the supported update/install workflow.

### 2026-07-12 VPS target preflight

- `abx.alanborger.com`, `dev.click.blue`, and `demo.workfra.me` currently have no public DNS records, so HTTPS deployment cannot yet complete.
- The existing Hetzner-backed `dev.alanborger.com` record resolves to `95.216.136.200`; the three requested A records should target that address unless the operator intends a different host.
- The configured Hetzner host is reachable. Its existing slot-2 `MyBusiness` cell is `create-workframe@0.1.7`, healthy for ten days, and reports secure `public_multi_user` posture; Caddy exposes it only at `dev.alanborger.com`.
- The host has approximately 6.4 GB available memory and 134 GB free disk. Workframe slots 3, 4, and 5 are unbound and can host the three requested cells after package publication, DNS, SMTP/invite configuration, and per-cell backup/restore planning are resolved.

From [final convergence synthesis](../../archive/planning/living-audit/final-convergence-synthesis.md):

1. **PackageTruthGate** — **done** (Alan sign-off MyBusiness Docker; WF-020 automates FirstRunEvidence JSON).
2. **Forced egress broker** — **done** (WF-025: compose + iptables enforcement; WF-027 broker audit events).
3. **Run ledger** — **landed** (WF-NS-P2: runs/run_events/run_line_items; chat, mention, kanban, cron, slash, webhook surfaces record; activity panel reads run_events). WF-016 receipt wiring is done; `amount_usd` remains null until pricing/billing work is admitted past the E stop line.
4. **Runtime adapter seam** — `runtime_kind` column + resolver; **deferred to E gate** (Hermes remains the only executable runtime this wedge).

## Explicitly deferred (north star)

- Cell manager / hosted provisioning
- Full tool broker beyond LLM + action proxy
- Billing line items / marketplace
- Non-Hermes engine adapters (Codex CLI, Pi, etc.) as first-class runtimes

## Public docs map

| Audience | Doc |
|----------|-----|
| Evaluator | [security.md](../public/security.md) → [audit.md](../public/audit.md) |
| Operator | [install.md](../public/install.md) → [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) |
| Contributor | [develop.md](../public/develop.md) → [AGENTS.md](../../AGENTS.md) |
