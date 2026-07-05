# Red team 05 — release gate and validation artifact risk

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
| Install docs | `docs/public/install.md` | `0ece45f99eb63781e090faefa670a61d3f33d265` |
| Public deploy checklist | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| Release-readiness pass | `docs/living-audit/release-readiness.md` | `3581c625be86e5e1fd7208c687c75af99115ea6d` |
| Refactor red team | `docs/living-audit/red-team-04-refactor-seam-risk.md` | `a5f8576d6784f50c6a02f3482befa33ec76bc86a` |
| Operator log | `operations/log.md` | `7de6a3f82e52ca10e0448116683532cff1c293aa` |

## Planning slice challenged

Adversarial review of `release-readiness.md`: whether the next small release can be called credible while local-only gates, public launch gates, funding policy, destructive install posture, and validation artifacts remain partly manual, skipped, or ambiguous.

## Current-state facts

- Public README and install docs still advertise `npx create-workframe@0.1.6`, while monorepo and installer package metadata are `0.1.7`.
- Install docs present `node scripts/workframe.mjs doctor` as an optional preflight, then `docker compose up -d --build` as the normal path.
- First boot includes deployment mode, public URL, SMTP/admin, integrations, model billing, model keys, native agent, invites, and launch.
- Harness ledger marks `installer-ui-bundle` and `dogfood-install-gate` as false and local/manual.
- Harness runner skips manual and `cursor-local` scenarios, so automated cloud verification cannot prove package release readiness.
- Public deploy docs require HTTPS, SMTP, generated secrets, secure mode, no Docker socket on API, dashboard gating, gateway env allowlisting, and verify script/manual smoke.
- Public deploy docs also state full Hermes terminal toolsets remain enabled on `/workspace`; isolation depends on profile RBAC, supervisor guards, vault, and proxy tokens.
- Release-readiness planning correctly defers non-Hermes adapters, but still depends on future evidence artifacts that are not yet canonicalized.

## Red-team contradictions / weak assumptions

### 1. A release gate that is skipped by the verifier is not a gate

`installer-ui-bundle` and `dogfood-install-gate` are the two most release-relevant checks, yet they are not enforced by the cloud harness. Treating green CI as release readiness would be a category error.

First-principles rule: the release gate must produce one artifact that cannot be confused with cloud CI:

```text
ReleaseEvidence
  package_version
  source_commit
  packed_tarball_name_or_hash
  fresh_target_path
  scaffold_exit_status
  ui_bundle_status
  wizard_completion_status
  first_chat_status
  public_gate_status_if_public
  operator
  timestamp
```

Without this, future agents will keep rediscovering the same distinction between `passes in cloud` and `safe package to install`.

### 2. `doctor` is overloaded before it is trusted

Install docs already expose `doctor` as optional preflight. The living audit wants a stricter mutation-free, redacted, context-labeled preflight. These are not the same thing unless proven by source and tests.

Safer wording for planning: existing `doctor` is a lifecycle health command until proven otherwise. Future `preflight_report` must not inherit trust from the word `doctor`.

### 3. Public launch readiness cannot be a one-time install fact

The release pass says public mode must fail closed. Good. The hidden issue is freshness. DNS, HTTPS, SMTP, proxy tokens, Docker socket posture, gateway env, firewall, and backup posture can drift after setup.

Rule: public release validation needs a live timestamped gate, not a persisted boolean.

```text
public_prereqs_configured != public_launch_verified_at
install_complete != public_launch_ready
first_chat_verified != safe_public_multi_user
```

### 4. Full terminal toolsets raise the standard for evidence

Public deploy docs are explicit: full Hermes terminal toolsets remain enabled on `/workspace`. That can be acceptable for a narrow, honest product if the workspace boundary, profile RBAC, supervisor path blocks, and vault/proxy boundaries are verified. It is not acceptable if release evidence only proves `/api/health` and first chat.

Minimum public smoke must include:

- member cannot access dashboard;
- gateway cannot resolve supervisor;
- API has no docker socket;
- gateway environment excludes auth/SMTP/supervisor secrets;
- member runtime access is restricted to own `u-{user}-*` profile;
- supervisor blocks direct `.env` and `auth.json` reads for protected profiles.

### 5. Funding policy is still too easy to treat as setup copy

Install docs include `Model billing — BYOK or company-pays`. Release-readiness says funding must be explicit before invites. The security invariant is stronger: every run needs a resolved payer before execution. A wizard setting alone is not enough for delegated loops, scheduled runs, or public teams.

Safer release posture: next release may persist team funding mode, but must not claim billing/audit correctness until `RunFundingDecision` and receipts exist.

### 6. Version drift is not just cosmetic

Version drift can make users install one artifact while docs and planning audit another. For a scaffold installer, this is not a typo-class issue; it breaks reproducibility of bug reports, dogfood evidence, and release sign-off.

Rule: no release evidence is valid unless it records both source commit and the exact package artifact used by `npx` or local pack.

## Hidden complexity inventory

| Release claim | Hidden evidence required |
|---|---|
| `install works` | Packed package, clean target, no stale monorepo artifacts, UI bundle served, wizard completes, first chat streams. |
| `public-ready` | Fresh HTTPS/SMTP/secrets/RBAC/network/env verification, not cached setup data. |
| `safe multi-user` | Invite-only auth, dashboard gating, profile RBAC, supervisor path guards, vault/proxy isolation. |
| `BYOK/company-pays` | Persisted setup decision now; per-run funding resolver later. |
| `doctor/preflight` | Mutation-free behavior, redaction, probe context, no raw paths/secrets in output. |
| `Hermes default not identity` | Public copy remains honest: Hermes is the only executable runtime today. |

## Security issues to pin before implementation

1. Do not call a release green while `installer-ui-bundle` or `dogfood-install-gate` remain false without an explicit no-release decision.
2. Do not let `doctor` imply adoption or safety until it is tested for no mutation and redaction.
3. Do not persist `public_launch_ready`; persist only evidence timestamps and rerun live checks before exposure.
4. Do not claim public multi-user safety from first-chat success alone.
5. Do not claim funding correctness from wizard copy alone; per-run funding decisions and receipts are separate future gates.
6. Do not let release evidence omit package artifact identity.
7. Do not make adapter-first public claims while only Hermes has executable evidence.

## Simpler first-principles alternative

```text
Next release definition:
  Release A: honest Hermes/Docker install package
    required:
      - version truth
      - packed package truth
      - bundled UI truth
      - clean install/wizard/first-chat truth
      - public deploy truth only if public mode is advertised as ready
    explicitly not included:
      - non-Hermes execution
      - broad runtime adoption
      - host Hermes import
      - billing-grade receipts

Planning after Release A:
  Release B: safety vocabulary
    - no-overwrite target gate
    - redacted preflight report
    - funding mode persistence
    - receipt state machine design

Only after B:
  Adapter expansion candidate
    - one second adapter with full start/stream/cancel/log/workspace/receipt proof
```

## Proposed migration / refactor steps

1. Amend release-readiness doctrine: cloud harness green is necessary but insufficient; release requires `ReleaseEvidence` artifact.
2. Define the release evidence artifact before changing code: markdown or JSON under a future release/audit path, generated manually at first.
3. Treat existing `doctor` as untrusted for future preflight until source review proves no mutation and output redaction.
4. Split release gates into `local_package_gate`, `public_launch_gate`, `team_funding_gate`, and `future_adapter_gate`.
5. Require package artifact identity in every release sign-off: version, source commit, packed tarball hash or npm dist tag, clean target path, and first-chat evidence.
6. Keep funding claims modest until `RunFundingDecision` and receipt lifecycle exist.
7. For public mode, require fresh live checks after every deploy or upgrade, not only install-time setup.

## Gaps / risks

- The current planning has good blocker lists, but not yet a canonical artifact that prevents agents from treating skipped/manual gates as optional.
- Public mode is security-sensitive because full terminal toolsets remain enabled; release evidence must prove boundaries, not just service health.
- `doctor` naming may cause future implementation to inherit trust from existing docs before the command is made mutation-free and redacted.
- Funding mode persistence is not the same as run-level funding resolution; public/team claims need this distinction.
- Version drift undermines reproducibility of every installer bug report and release claim.

## Next best red-team target

Test/validation plan for installer journeys: challenge whether each branch can be proven with fixture tests and release artifacts without touching user homes, leaking paths, relying on cloud-only harness, or confusing first-chat success with public/team safety.
