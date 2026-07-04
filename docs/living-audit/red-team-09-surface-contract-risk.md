# Red team 09 — surface contract, release claims, and false-OS risk

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Entry | `README.md` | `b97cd64e4f899dc758bb73a0e04ec9a89a344317` |
| Agent rules | `AGENTS.md` | `f648f29fdb9569c3bb7a5c6c8e178173582cde03` |
| Repo map | `START_HERE.md` | `cf65246dc937256099d8297e79487635c3b724d2` |
| Harness docs | `.harness/README.md` | `e21ce2d468b8f8baaa4660edf7054bd04d4f7ec0` |
| Harness scenarios | `.harness/feature_list.json` | `ed32c988e668d813e99d8f332ebd2d22b3fbb95e` |
| Harness runner | `.harness/verify.mjs` | `e8785ebc99091abfa295e9062613c4db208c840f` |
| Monorepo package | `package.json` | `7b8232a887d2c3558078c18cbbc6cac20051f363` |
| Installer package | `packages/create-workframe/package.json` | `72fc7bf7625c8e786baf0f9d44c389e5f4ad6547` |
| Docs index | `docs/README.md` | `e8a2a847ef29f784655f348fb1a53e535ff4915e` |
| Using docs | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| API docs | `docs/public/api-reference.md` | `8ac837776545924e941b3660f1938406f2a4d23c` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Workspace layout | `apps/web/src/components/workspace/DockviewWorkspace.tsx` | `1d5a7bbca7079492f859ea1cdc668efd4780aca2` |
| Latest planning pass | `docs/living-audit/workframe-surface-baseline.md` | `6d5e877363c6cdbd69413d1f5b5b03c4c8c4b5d7` |
| Previous red-team pass | `docs/living-audit/red-team-08-manifest-authority-risk.md` | `a5015dffbafd741576d27d0fdad8ffeb869605f1` |
| Deployment order plan | `docs/living-audit/deployment-order.md` | `88c8105212bff0c2f2b7974826d63cce62f58e58` |
| Existing-runtime policy | `docs/living-audit/existing-runtime-adoption-policy.md` | `563631b5e23b8d608c0a7cf3e21f8c7371d6093f` |
| Operator log | `operations/log.md` | `952c5f2ef8ccf53efe057a904300c770a52fb21d` |

## Planning slice challenged

Adversarial review of `workframe-surface-baseline.md`: whether the proposed five-panel baseline actually reduces product risk, or whether public docs, API routes, and surface naming still create a false impression of a complete multi-user social OS.

## Current-state facts

- README currently describes Workframe as a multi-user web shell around Hermes with UI, API, installer, and Docker Compose.
- The actual dock workspace initializes five panels: agent rail, chat, files, browser, and activity.
- Public using docs claim a broader surface: rooms/spaces, DMs, activity, files, browser, team rail, chat, create agent, model picker, skills, slash commands, profile/account connection, per-user runtime, members/invites, stack-managed keys, Hermes dashboard, @mentions, agent DMs, and Kanban.
- API docs list routes for workspace members, invites, rooms, messages, live agent turns, workspace events, Hermes profiles/chat/models/skills/commands, files, health, first-run setup, and auth.
- Security docs make public multi-user controls material to the product boundary: HTTPS, SMTP, vault KEK, proxy token, supervisor token, invite-only auth, owner/admin dashboard, runtime RBAC, allowlisted gateway env, and supervisor path blocking.
- Harness evidence remains cloud/backend focused, while local-only installer UI bundle and full dogfood install-gate are still false or manual.
- The latest planning pass correctly narrows v0.1.x to a five-panel spine plus explicit unavailable/not-configured states, with non-Hermes runtimes inert.

## Red-team contradictions / weak assumptions

### 1. Five panels do not equal five stable products

The surface baseline says the five panels are the v0.1.x product spine. That is a useful simplification, but each panel is a gateway to larger claims:

```text
agent rail -> identity + runtime + provider + funding + profile isolation
chat       -> stream + stop + steer + receipt + no-key handling + safety
files      -> path authority + writes + uploads + browser preview + audit
browser    -> artifact rendering + local/remote trust boundary
activity   -> event semantics + privacy + receipts + team visibility
```

A five-panel UI can still hide ten hard systems. The release rule should be: a panel is not a product promise unless its failure modes are bounded and its evidence gate exists.

### 2. Public docs still over-promise the Workframe OS

The latest planning document says v0.1.x should not ship a broad agentic OS by label. But `docs/public/using-workframe.md` still reads as if Workframe already provides the broader team workspace surface. That may be aspirationally correct, but it weakens release truth unless docs classify each item as `available`, `Hermes-backed`, `preview`, `admin-only`, `mode-gated`, or `planned`.

Risk: users evaluate the product against the public social-OS promise, not the narrower managed-Hermes package truth.

### 3. Activity is dangerous if it is decorative

The activity panel is positioned as a core product surface. If it shows generic feed noise or only partial actions, it can create false audit confidence. For v0.1.x, activity should be either:

```text
minimal audit spine: install/setup/provider/profile/chat/file events with actor + scope + timestamp
```

or it should be labeled as a preview. A vague activity stream is worse than no activity stream because users may infer accountability that does not exist.

### 4. Files/browser are authority surfaces, not convenience panels

The baseline correctly restricts files to generated `Files/`, but public docs say files are under `/workspace`. A user will not know whether `/workspace`, generated `Files/`, Hermes workspace, browser preview, upload, and file write routes share the same boundary. This is a path-authority risk.

Forbidden shortcut:

```text
files panel renders -> filesystem boundary is safe
browser preview works -> artifact authority is safe
```

The release needs a named `WorkspacePathAuthority` before expanding browser/file claims.

### 5. Skills and slash commands still sound Workframe-native

The planning pass says skills and commands should be labeled managed-Hermes capabilities in v0.1.x. Public docs still call slash commands `Workframe-native command palette (subset of Hermes CLI)`. That is an ambiguous sentence: native to Workframe, or proxied from Hermes?

Simpler copy rule: until an adapter-neutral command model exists, call them `Hermes-backed skills` and `Hermes-backed slash commands`; do not call them Workframe-native.

### 6. Team/admin surfaces are too close to release-critical security

Members, invites, stack-managed keys, dashboard proxy, per-user runtime, and public multi-user controls are listed as product features. They are not optional polish in a public multi-user install; they are security-critical. If any one is only partially verified, the public mode should remain blocked.

### 7. Surface availability can become another weak manifest

`SurfaceAvailability` is a good proposed type, but it risks becoming a static label disconnected from proof. Availability must be computed from evidence, mode, role, runtime, provider state, and safety gates, not hardcoded as release copy.

Bad pattern:

```text
surface.status = available
```

Better pattern:

```text
surface.status = derive(mode, role, runtime_health, provider_status, evidence_gate, path_authority, security_gate)
```

## Hidden complexity inventory

| Surface | Hidden failure mode | Simpler posture |
|---|---|---|
| Agent rail | Implies multiple executable agents/runtimes | Show one managed Hermes lane; other candidates only in doctor/preflight. |
| Chat | No-key, no-runtime, failed stream, stop/steer ambiguity | First chat smoke plus explicit no-key and stop/steer gates. |
| Files | Path escape, upload authority, shared tree confusion | One generated `Files/` root with no traversal and visible scope label. |
| Browser | Renders unsafe or wrong-origin artifacts | Preview only workspace artifacts; no remote browsing claim. |
| Activity | Decorative feed mistaken for audit | Minimal audit events or preview label. |
| Kanban/goals/loops | Becomes second source of truth | Files are truth; Kanban/goals/loops are artifacts until domain model exists. |
| Skills/commands | Hermes-specific features marketed as Workframe-native | Label as Hermes-backed and allowlisted. |
| Team/admin | Feature framing hides security gates | Public mode blocked until invite/domain/SMTP/RBAC/dashboard evidence exists. |
| Provider/funding | Model picker hides who pays | Show funding policy before run; receipt after run later. |

## Simpler first-principles alternative

Define a `SurfaceContractGate` before broad public release claims:

```text
SurfaceContractGate
  surface_id
  mode_scope: local | trusted_team | public_multi_user | remote_client
  role_scope: owner | admin | member | guest
  execution_scope: managed_hermes | no_runtime | inert_candidate
  data_scope: Files/ | profile_state | vault_status | workspace_events
  user_claim
  unavailable_claim
  evidence_gate
  security_gate
  audit_event_required
  copy_label
```

Then require every visible feature in public docs to map to one of:

```text
available_with_gate
mode_gated
admin_only
Hermes_backed
preview
planned
```

No surface should be listed as a generic Workframe feature until it has a `SurfaceContractGate` row.

## Security issues to pin before implementation

1. Activity must not imply audit completeness unless it records actor, scope, timestamp, action, target, and outcome for release-critical actions.
2. Files/browser must display and enforce the same workspace root; users should not see both `Files/` and `/workspace` without a clear mapping.
3. Slash command execution should be allowlisted and receipt-bearing before public multi-user mode.
4. Team/admin features must be hidden or blocked in local/single-user modes rather than half-visible.
5. Public docs must not present inert runtime candidates or adapter-neutral skills as working execution paths.
6. The Hermes dashboard proxy should not be marketed as an ordinary admin feature unless owner/admin gating is proven in public mode.
7. Surface status must be computed from gates, not maintained as optimistic documentation.

## Proposed migration / refactor steps

1. Add a planning-only `SurfaceContractGate` spec and map the five panels first.
2. Change public docs to classify each surface: `available`, `Hermes-backed`, `preview`, `mode-gated`, `admin-only`, or `planned`.
3. Define release-blocking events for the activity panel: install completed, setup completed, provider status changed, profile created, chat started/stopped/failed, file written/uploaded, invite sent.
4. Define `WorkspacePathAuthority`: one visible root label, no traversal, upload/write scope, browser preview scope, audit on mutation.
5. Reclassify skills/slash commands as Hermes-backed until adapter-neutral contracts exist.
6. Keep Kanban/goals/loops file-backed or preview-only until they have canonical domain authority.
7. Do not add more panels before the five-panel spine has evidence gates.
8. Treat public multi-user as blocked unless team/admin/security surfaces pass a public launch gate.

## Diagnostic conclusion

The surface baseline is directionally correct but still too easy to over-sell. The risk is not that Workframe has too many panels; it is that each panel compresses several authority, security, and evidence boundaries. The next convergence pass should turn the five-panel spine into a `SurfaceContractGate` matrix before adding multi-user funding or second-runtime adapter claims.

## Next best planning target

Multi-user/BYOK/company-pays journey, but constrained by surface contracts: who can see provider status, who can trigger a run, who pays, what appears in activity/audit, and what remains hidden in local versus public mode.
