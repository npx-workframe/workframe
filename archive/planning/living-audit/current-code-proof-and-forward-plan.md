# Current code proof and forward implementation plan

Temporary living-audit planning material. Not public release doctrine. This plan converts the 24-run rail, `25-audit.md`, and the Softsupply north-star brief into an implementation path that first proves and patches the current code, then advances toward the Workframe Cell product.

## North-star alignment

Workframe should become a private autonomous business cell where humans and persistent agents collaborate around files, boards, chat, schedules, and controlled computer runs.

The stable Workframe-owned primitives are:

```text
cells
identity
workspaces / rooms
agents
files / artifacts
runs
capabilities / leases
brokers
policies
audit
billing / cost attribution
```

The replaceable substrates are:

```text
Hermes
Claude CLI
Codex
Cursor
Copilot
OpenCode / OpenClaw
models
local daemons
Docker / VPS / BYOC runners
payment rails
cloud providers
```

Implementation rule:

```text
Do not jump from Hermes-centered v0.1.x directly to universal runtime OS.
First prove the current installable package. Then add cell authority, detection, and inert adapters. Then make one second runtime executable.
```

## Strategic answer to the installation question

The target user-facing path should eventually be:

```text
npx create-workframe MyBusiness
# or Electron download

1. Create or open a Workframe Cell.
2. Detect environment without mutation.
3. Choose deployment mode: local, Docker trusted team, VPS self-host.
4. Choose funding: BYOK, company-pays, or later hybrid.
5. Create default managed-Hermes runtime if no executable runtime exists.
6. Record other CLIs/runtimes as inert candidates until adapters are proven.
7. Complete first-run setup.
8. Launch Workframe cockpit: agent rail, chat, files, browser, activity.
9. Later expose boards, goals, skills, slash commands, loops, and audit once contracts exist.
```

But the current code should not claim all of that yet.

The next release should claim only:

```text
Clean empty-directory install -> managed Hermes Docker -> single-user BYOK first chat.
```

Everything else is either detection-only, documented preview, or v0.2+.

## Phase 0 — freeze scope and stop claim drift

Goal: prevent product language from outrunning proof.

### Tasks

1. Add a `release_scope.json` or markdown scope file declaring what v0.1.x proves:
   - clean empty target only;
   - managed Hermes Docker only;
   - single-user local first-run path;
   - explicit BYOK credential path;
   - no executable host-runtime adoption;
   - no second runtime execution;
   - no company-pays/hybrid runtime execution;
   - no Electron-native setup claim;
   - no public VPS production-ready claim.

2. Add a docs-claim verifier:
   - README/install docs must not imply unsupported runtime adapters are executable.
   - Team/public/VPS/company-pays claims must be labeled planned/manual/experimental unless evidence exists.
   - Install command version must match package metadata.

3. Patch obvious drift:
   - align README install command;
   - align `docs/public/install.md` command;
   - align release docs/package metadata/tag.

### Definition of done

- `pnpm verify:public` or equivalent fails on version drift.
- Public docs say exactly what is proven.
- The release scope is machine-readable or trivially parseable.

## Phase 1 — PackageTruthGate evidence spine

Goal: prove current code without relying on source-tree optimism.

### 1A. Evidence schema

Create:

```text
operations/release-evidence/schema/package-truth-gate.schema.json
operations/release-evidence/examples/package-truth-gate.example.json
```

Evidence envelope:

```json
{
  "gate_name": "PackageTruthGate",
  "schema_version": "0.1",
  "git_ref": "...",
  "package_version": "...",
  "decision": "allow|deny|needs_user_action",
  "install_evidence": {},
  "first_run_evidence": {},
  "negative_install_evidence": [],
  "docs_claim_evidence": {},
  "redactions": []
}
```

Each step uses:

```text
asserted | not_asserted | failed
```

not only booleans.

### 1B. PackageInstallEvidence runner

Add a maintainer script, likely under:

```text
scripts/workframe/package-truth-gate.mjs
# or
packages/create-workframe/scripts/package-install-evidence.mjs
```

It should:

```text
read root package version
read installer package version
verify README/install docs version agreement
build or assert web bundle
run npm pack for create-workframe
install from packed tarball into clean temp dir
run scaffold assertions against generated output
record package tarball digest
record generated manifest package version
record UI asset/build identity when available
write PackageInstallEvidence JSON
```

This does not need a model key.

### 1C. NegativeInstallEvidence runner

Add negative cases:

```text
unsafe project name denied
non-empty target denied
existing arbitrary directory denied without mutation
existing Workframe manifest detected read-only
missing Docker -> needs_user_action, not partial install
host runtime candidate -> detected_only, no import
```

Each case records:

```text
before_hash
after_hash
mutation_observed: false|true
recovery_text_present: true|false
decision
reason
```

### 1D. FirstRunEvidence runner

Local/manual first is acceptable if fully recorded.

It should prove:

```text
Docker compose boot
API health
supervisor health
managed Hermes health
setup wizard completion for single_user_local
explicit BYOK path accepted
first chat returns or streams
minimal session/activity/receipt exists
no host CLI auth import occurred
```

If model credentials are unavailable, the decision is `needs_user_action`, not green.

### Definition of done

`PackageTruthGate` cannot pass unless:

```text
PackageInstallEvidence.allow
NegativeInstallEvidence.deny_cases_green
FirstRunEvidence.allow OR explicitly manual-blocked with reason
DocsClaimEvidence.allow
```

## Phase 2 — patch current bugs and inconsistencies found by the gate

Goal: use evidence failures to patch actual current-code issues.

Expected likely patches:

1. Version drift:
   - README install command;
   - `docs/public/install.md` command;
   - package metadata/tag/release docs.

2. UI package parity:
   - expose `WORKFRAME_API_VERSION`, package version, build id, or asset manifest digest in generated UI/config;
   - record this in evidence.

3. Installer target handling:
   - ensure non-empty target denial is pre-mutation;
   - distinguish existing Workframe cell from arbitrary non-empty dir;
   - add recovery text.

4. Harness behavior:
   - keep cloud verify fast, but add release sign-off script that reports local/manual evidence missing as blocked;
   - avoid marking release green when `installer-ui-bundle` or `dogfood-install-gate` is absent.

5. Public docs:
   - describe v0.1.x as managed-Hermes Docker path;
   - mark public/VPS/team/company-pays as setup branches that require separate evidence.

### Definition of done

Every patch has a corresponding failing evidence case before the fix and passing evidence after the fix.

## Phase 3 — CellAuthorityGate and mutation-free doctor

Goal: support the future `create/open/update/connect/adopt` world without overwriting existing setups.

### CellAuthorityGate

Create a design doc first, then code.

Cell manifest should include:

```text
cell_id
schema_version
created_by_package
package_version
install_mode
install_root
layout: Agents / Files / workframe-api / workframe-ui / supervisor
managed_runtime: hermes_docker
provenance_digest
created_at
last_opened_at
```

Lifecycle states:

```text
no_cell_detected
empty_target_create_allowed
existing_cell_read_only_open
foreign_non_empty_target_denied
cell_update_plan_required
connect_requires_explicit_plan
adopt_requires_explicit_plan
```

### Mutation-free doctor

Add:

```text
node scripts/workframe.mjs doctor --json
```

Output should include only redacted readiness signals:

```json
{
  "docker": { "present": true, "ready": true },
  "node": { "present": true },
  "workframe_cell": { "present": true, "manifest_valid": true },
  "managed_hermes": { "present": true, "executable": true },
  "host_runtime_candidates": [
    { "kind": "claude_cli", "present": true, "state": "candidate_detected" },
    { "kind": "codex", "present": true, "state": "candidate_detected" }
  ],
  "provider_candidates": [
    { "kind": "openai", "redacted": true, "state": "candidate_detected" }
  ],
  "forbidden_probe_attempts": []
}
```

Doctor must not:

```text
read token files
copy config
write profile envs
import host auth
start host runtimes
mutate existing cells
```

### Definition of done

- Doctor has unit tests with fake home dirs.
- Host runtime detection returns redacted candidates only.
- Existing Workframe cell opens read-only.
- Update/connect/adopt remain blocked until explicit plan exists.

## Phase 4 — RunAuthorityGate for current Hermes path

Goal: make current execution safe before team/company funding and loops.

Add a first-class pre-run decision object:

```text
RunAuthorityDecision
  actor_user_id
  profile_owner_user_id
  workspace_id
  room_id/card_id/session_id
  runtime_kind = managed_hermes for v0.1.x
  provider_kind
  provider_user_only
  credential_binding_id
  funding_mode
  payer_scope
  delegation_scope
  decision
  reason
```

Rules:

```text
single_user_local -> BYOK only
trusted_team BYOK -> actor must own credential or have execute grant
company_pays -> admin opt-in, visible payer, no user_only fallback
hybrid -> disabled until receipts exist
```

Integrate with existing `wf_rt_` turn leases:

```text
RunAuthorityDecision.allow -> issue wf_rt_ lease
RunAuthorityDecision.deny -> no lease, visible reason
```

### Definition of done

- Unit tests for BYOK self-run.
- Unit tests for delegated run without key access.
- Unit tests for `user_only` provider no workspace fallback.
- FirstRunEvidence records the authority decision.

## Phase 5 — SurfaceContractGate for product spine

Goal: ensure Workframe UI surfaces work out of the box with any supported setup, without pretending every future surface is complete.

v0.1.x product spine:

```text
agent rail
chat
files
browser
activity
```

Each surface gets a compact contract:

```text
surface name
reads
writes
authority gate
runtime dependency
evidence emitted
known limitations
release claim allowed
```

Future surfaces:

```text
kanban
goals
skills
slash commands
loops
audit
```

These should be either:

```text
implemented + evidence-backed
or visible as planned/experimental/manual
```

### Definition of done

- One contract file per surface or one matrix.
- PackageTruthGate confirms the five-panel spine loads.
- Docs claim only evidence-backed surfaces.

## Phase 6 — inert runtime adapter model

Goal: let Workframe become the unifying interface without touching user setups.

Add config-only `RuntimeBinding` candidates:

```text
candidate_detected
binding_declared
adapter_harness_green
executable_runtime
first_run_verified
selectable_default
```

Kinds:

```text
managed_hermes_docker
host_hermes
claude_cli
codex_cli
cursor
copilot
opencode
openclaw
local_daemon
remote_runner
```

v0.1.x/v0.2 rule:

```text
Only managed_hermes_docker is executable until another adapter harness proves start/stream/cancel/log/receipt.
```

### Definition of done

- Doctor can list candidates.
- UI can show candidates as detected/inert.
- No non-Hermes runtime can be selected for execution until harness proof exists.

## Phase 7 — one second adapter, not many

Goal: validate the adapter-first design with one non-Hermes path.

Pick one based on lowest proof cost:

```text
Option A: Codex CLI OAuth path
Option B: Claude CLI local path
Option C: OpenCode/OpenClaw local path
```

Adapter harness requirements:

```text
start
stream or collect output
cancel
log events
record runtime identity
record credential source class
produce run receipt
failure modes
no host config mutation
```

### Definition of done

- One non-Hermes runtime reaches `first_run_verified`.
- Agent profile can declare runtime/provider/model separately.
- UI shows clear runtime selection and limitations.

## Phase 8 — deployment branches

Only after the local managed-Hermes proof is stable.

### Local

```text
empty target create
managed Hermes Docker or local runtime candidate detection
BYOK
single-user
first chat
```

### Docker trusted team

```text
invite user
each user BYOK
per-user runtime profile
workspace files visible to team
run receipts visible
trusted-team disclaimer
```

### VPS self-host

```text
domain check
HTTPS setup
SMTP check
invite/domain allowlist
backup/restore evidence
public-mode config evidence
```

### Electron

Electron should not own core setup first.

Recommended posture:

```text
Electron = shell/client for an existing or newly created Workframe Cell.
Installer/core lifecycle remains shared with npx path.
```

Electron can later provide a friendlier UI over:

```text
create cell
open cell
doctor
start/stop
connect provider
show evidence
```

## Implementation order

### Milestone A — prove current package

1. Version agreement verifier.
2. Release scope file.
3. Evidence schema and example.
4. PackageInstallEvidence runner.
5. NegativeInstallEvidence runner.
6. FirstRunEvidence runner/manual harness.
7. Docs-claim gate.
8. Patch failures found by the gate.

Exit criterion:

```text
A clean user can install exact package version into empty target, boot stack, complete single-user setup, connect explicit BYOK, and run one managed-Hermes chat, with evidence.
```

### Milestone B — safe lifecycle

1. CellAuthorityGate design.
2. Manifest provenance fields.
3. Read-only open.
4. Deny arbitrary non-empty targets.
5. Mutation-free doctor.
6. Detected-only host runtime candidates.

Exit criterion:

```text
Workframe can inspect existing environments without mutation and without implying adoption/execution.
```

### Milestone C — authority for teams

1. RunAuthorityGate.
2. BYOK/company-pays policy tests.
3. Visible payer before run.
4. Minimum run receipt.
5. Surface contracts.

Exit criterion:

```text
Team runs have explicit actor, runtime, credential, payer, and receipt semantics.
```

### Milestone D — adapter-first v0.2

1. RuntimeBinding candidate model.
2. Agent profile separates identity/provider/model/runtime.
3. One second runtime adapter harness.
4. First verified non-Hermes run.

Exit criterion:

```text
Workframe proves it can govern at least two runtime substrates without making Hermes the product identity.
```

## Non-goals until the gates exist

Do not implement yet:

```text
universal runtime adoption
automatic host config import
company-pays hybrid fallback
public SaaS multi-tenant claims
marketplace
agent-to-agent payments
full egress broker
full file manifest isolation
enterprise BYOC
```

These are valid north-star directions, but not next-release work.

## Final recommendation

The implementation path should be:

```text
1. Prove current installable Workframe.
2. Patch drift and evidence failures.
3. Add cell authority and mutation-free detection.
4. Add run authority and surface contracts.
5. Add inert adapter candidates.
6. Prove exactly one second runtime.
7. Then expand deployment, marketplace, billing, and enterprise layers.
```

This preserves the current Hermes-centered product, avoids a rewrite, and moves toward the Softsupply doctrine: Workframe owns cells, runs, identity, files, policies, brokers, audit, and business state; runtimes and CLIs remain replaceable.
