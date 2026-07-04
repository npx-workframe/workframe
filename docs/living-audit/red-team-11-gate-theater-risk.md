# Red team 11 — gate-theater, evidence, and decision-owner risk

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
| Latest synthesis | `docs/living-audit/final-convergence-synthesis.md` | `23c373f0cb5d776337e4a9a33e0ce47d3a844a2f` |
| Previous red team | `docs/living-audit/red-team-10-funding-authority-risk.md` | `ee12fbd969b145147e009b75dd32fc4ee978fea2` |
| Operator log | `operations/log.md` | `d4c38e60bd404ae03dd1c469ed968b824859c1df` |

## Planning slice challenged

Adversarial review of the final convergence synthesis: whether the proposed gates are real decision systems or just renamed uncertainty around package truth, cell authority, surface contracts, run authority, and adapter readiness.

## Current-state facts

- The latest synthesis correctly narrows v0.1.x to managed Hermes Docker and defers executable non-Hermes adapters.
- It defines several named gates: `PackageTruthGate`, `CellAuthorityGate`, surface contract gate, `RunAuthorityGate`, and adapter readiness state.
- It still leaves unclear which component owns each gate, where evidence is written, how denial states are surfaced, and which negative tests prove the gate is not decorative.
- The prior red-team pass reframed funding as credential authority and required a pre-run allow/deny decision before runtime invocation.
- `operations/log.md` shows the planning rail has produced many compact diagnostics, but the living-audit layer remains prose until release evidence artifacts and failing tests exist.

## Red-team contradictions / weak assumptions

### 1. A named gate is not a gate unless it can block

The synthesis names the right gates, but a gate that only appears in docs cannot protect release, install, update, or runtime execution.

Minimum bar:

```text
gate(input) -> allow | deny | needs_user_action
  emits evidence
  has an owner
  has negative tests
  blocks the next state
```

If a release checklist says `PackageTruthGate` but publishing can proceed without the evidence artifact, the gate is theater.

### 2. Gate ownership is missing

The plan currently mixes installer, API, supervisor, UI, harness, and docs responsibilities. Without explicit ownership, each gate can be assumed to be someone else's job.

Risky ambiguity:

| Gate | Current risk |
|---|---|
| `PackageTruthGate` | npm packaging, installer, UI bundle, API health, and first chat span too many owners. |
| `CellAuthorityGate` | installer may own creation, API may own runtime access, UI may own open/update UX. |
| Surface contract gate | UI can show panels before backend authority/evidence semantics exist. |
| `RunAuthorityGate` | provider selection, credential leasing, delegation, and receipt may split across API/supervisor/runtime. |
| Adapter readiness | detection can look like support even when no execution harness exists. |

### 3. Evidence shape is underdefined

`emit evidence artifact` is not enough. Evidence needs a canonical schema and a stable location. Otherwise agents will produce screenshots, logs, markdown notes, or CI summaries that cannot be compared.

Better minimal schema:

```text
EvidenceArtifact
  schema_version
  git_ref
  package_version
  scenario_id
  gate_name
  input_summary_redacted
  decision
  denial_or_success_reason
  command_or_probe_executed
  observed_outputs_redacted
  artifact_paths
  timestamp
```

### 4. Negative cases are more important than happy paths

The synthesis correctly asks for package truth and first chat. The risk is overfitting to one green path. The release should also prove denials:

```text
missing Docker -> guided block, no partial cell
existing non-empty target dir -> explicit deny/plan, no overwrite
host Claude/Codex detected -> inert candidate, no token read, no execution
BYOK missing key -> deny, no workspace fallback in BYOK mode
user_only provider + workspace key -> deny before runtime invocation
```

### 5. `doctor --json` can become a new authority bypass

A mutation-free doctor is safer than an installer probe, but users and agents may treat `doctor says ready` as permission to act. Doctor output must remain advisory unless passed through the relevant gate.

Safer rule:

```text
doctor = observation
manifest = provenance
plan = proposed mutation
gate = authority to mutate or run
```

### 6. Read-only open is harder than it sounds

`open may inspect` appears safe, but opening a cell can still trigger migrations, service starts, lock writes, browser sessions, profile creation, or background health repair unless the code path is deliberately frozen.

Read-only open needs an explicit invariant:

```text
open --read-only
  no file writes
  no container changes
  no profile creation
  no credential probe beyond redacted presence
  no runtime invocation
  no repair
```

### 7. Surface contracts must include absence semantics

The five-panel spine is plausible, but surfaces should not only define what works. They must define what is hidden, disabled, or shown as pending when authority/evidence is missing.

Example:

```text
files panel can read workspace files
files panel cannot mutate outside cell root
files panel shows locked state when CellAuthorityGate denies mutation
activity panel shows gate decisions, not inferred optimism
```

### 8. Adapter candidates should not share labels with executable runtimes

If UI copy says `Codex detected`, users may assume Workframe can run Codex. The state name should be visibly inert.

Safer labels:

```text
Detected only
Config candidate
Harness verified
Executable
Selectable default
```

No candidate should appear in agent profile runtime selection until it is at least `Harness verified`, and no default until `first_run_verified`.

## Hidden complexity inventory

| Area | Hidden failure mode | Simpler posture |
|---|---|---|
| Gates | Names replace enforcement | Define owner, input, output, blocker, evidence, negative test. |
| Evidence | Markdown proof cannot be compared | One schema, one folder, deterministic scenario ids. |
| Doctor | Advisory probe becomes permission | Doctor never mutates and never authorizes by itself. |
| Open | Read-only path quietly repairs | Separate inspect mode from repair/update/connect. |
| Surfaces | Panels imply capability | Disabled states are part of the contract. |
| Adapter detection | Presence reads as support | Use `detected-only` language until harness green. |
| Funding | Receipt omits authority decision | Receipt derives from pre-run gate decision. |
| Release | Cloud green hides install failure | Package truth evidence blocks release claim. |

## Simpler first-principles alternative

Collapse the next proof into one linear release spine:

```text
PackageTruthGate
  -> CellAuthorityGate(create clean cell only)
  -> SurfaceContractGate(five panels, no OS expansion)
  -> RunAuthorityGate(single-user BYOK, managed Hermes only)
  -> FirstRunReceipt(first chat evidence)
```

Everything else is outside the release spine:

```text
open/update/connect/adopt = inspect-only or deferred
team/company/hybrid = policy docs only until RunAuthorityGate is implemented
non-Hermes runtimes = detected-only until adapter harness green
Electron/VPS/public = checklist only until package truth is repeatable
```

This is less ambitious but more falsifiable.

## Gate definition template

Every future planning or implementation ticket should include:

```text
GateName
  owner_component:
  allowed_inputs:
  forbidden_inputs:
  decision_values:
  evidence_path:
  user_visible_state:
  blocks:
  negative_tests:
  deferrals:
```

No new named gate should be accepted without those fields.

## Proposed migration / refactor steps

1. Turn `PackageTruthGate` into the only v0.1.x release-blocking artifact before expanding any installer branch.
2. Define a canonical `docs/living-audit/evidence-schema.md` or future `operations/release-evidence/` schema before more evidence is produced.
3. Add negative release scenarios to the validation plan: missing Docker, non-empty target, detected host runtime, missing BYOK key, forbidden workspace fallback.
4. Keep `doctor --json` advisory and explicitly non-authoritative.
5. Define `open --read-only` invariants before any update/connect/adopt behavior.
6. Require surface contracts to include disabled/locked/error states, not just happy-path capabilities.
7. Rename adapter UI states to make inert status impossible to mistake for support.
8. Require every run receipt to reference the pre-run `RunAuthorityDecision`.
9. Defer Electron/VPS/public/team claims until the release spine produces comparable evidence.

## Diagnostic conclusion

The convergence plan is directionally strong, but it has reached the point where more named gates can create false confidence. The next failure mode is not architectural imagination; it is unverifiable authority. A credible v0.1.x path should define one linear release spine, one evidence schema, explicit gate ownership, and negative tests that prove unsafe actions are blocked.

## Next best planning target

Final red-team synthesis: consolidate the 12-run diagnostic into a short release-threat model and a ranked list of blockers that must become implementation tickets before v0.1.x is marketed as installable.