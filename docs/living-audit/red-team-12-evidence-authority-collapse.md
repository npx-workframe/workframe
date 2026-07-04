# Red team 12 — evidence authority collapse and release-spine risk

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Entry | `README.md` | `b97cd64e4f899dc758bb73a0e04ec9a89a344317` |
| Final convergence synthesis | `docs/living-audit/final-convergence-synthesis.md` | `23c373f0cb5d776337e4a9a33e0ce47d3a844a2f` |
| PackageTruthGate memo | `docs/living-audit/package-truth-gate.md` | `e99a53369170fa559b5918ff43de38175081bc5a` |
| Previous red team | `docs/living-audit/red-team-11-gate-theater-risk.md` | `3b291251695a4907b6c545e21dbb7d70dc418da5` |
| Operator log | `operations/log.md` | `a50d6e9a670c7fc0c5edc033ab394446298705c2` |

## Planning slice challenged

Adversarial review of the new `PackageTruthGate` release memo: whether packed-package first-chat evidence is sufficient, or whether the gate still collapses several independent authority, installer, credential, and UX problems into one green artifact.

## Current-state facts

- The public README still advertises `create-workframe@0.1.6` while the living-audit notes package metadata at `0.1.7`; version agreement remains a release-trust blocker.
- The convergence synthesis says v0.1.x should prove a clean packed-package install, wizard, UI bundle, health checks, and one first chat through managed Hermes Docker.
- The `PackageTruthGate` memo scopes out Electron, VPS production, company/hybrid funding, host runtime execution, open/update/connect/adopt mutations, and non-Hermes adapters.
- The previous red-team pass warned that gates without owner, evidence schema, blocker, and negative tests are theater.
- The new memo improves this by adding a gate contract and minimal JSON evidence schema, but the contract still mixes installer, package, Docker, UI, API, supervisor, Hermes, credentials, and user-journey success into a single pass/fail.

## Red-team contradictions / weak assumptions

### 1. First chat is not one proof; it is a chain of proofs

A single `first_chat_ok: true` can hide multiple weaker claims:

```text
package installed
  -> generated cell is sane
  -> Docker stack booted
  -> UI served matching bundle
  -> setup state persisted
  -> provider credential was accepted safely
  -> API routed to supervisor
  -> supervisor routed to managed Hermes
  -> response streamed or returned
  -> receipt/activity recorded
```

If the evidence schema records only booleans, later agents cannot know which layer failed or which layer was never asserted.

### 2. `clean target creation only` dodges the real user journey

The simplest safe release path is clean create, but real users rerun installers, mistype target paths, create inside existing repos, and try to open prior cells. A release that only proves clean create is honest only if marketing says `new empty directory only`.

Sharper posture:

```text
v0.1.x installable claim = clean empty target only
existing directory = denied with recovery text
existing Workframe cell = read-only detection only
anything else = blocked, not repaired
```

### 3. Credential success can accidentally become credential capture

The gate requires one first chat, which requires a usable model credential or session. The dangerous shortcut is letting the gate read host auth/config because it is convenient.

Required invariant:

```text
release evidence may prove that a credential binding works
release evidence must not copy, display, persist raw, or import host credentials
host CLI/session detection remains detected-only
```

The evidence artifact should include only redacted credential source class, never token path, env value, OAuth session contents, or provider secret.

### 4. UI bundle parity is necessary but under-specified

`ui_loaded: true` and `UI bundle parity` are not enough. Parity should mean the package-generated install serves the same expected build identity as the packed artifact. Otherwise a stale copied bundle can load while the source tree is green.

Minimum evidence field:

```text
ui_build_id | package_digest | generated_asset_manifest_digest
```

If no build identity exists yet, the gate should explicitly record `not_asserted`, not silently pass.

### 5. Negative tests need denial evidence, not just expected names

The memo lists negative cases, but the evidence schema permits `{ id, decision }` only. That is too thin. A denial proof needs observed non-mutation.

Better negative case shape:

```json
{
  "id": "non_empty_target",
  "decision": "deny",
  "reason": "target_not_empty",
  "mutation_observed": false,
  "user_recovery_text_present": true,
  "forbidden_side_effects_observed": []
}
```

### 6. Public docs can still overclaim while gates are local-only

The gate scopes out VPS/public/team execution, but README and docs language may still imply multi-user readiness because Workframe is described as a multi-user shell. The release gate should block not only npm publish/sign-off but also public wording that implies deferred branches are supported.

Simpler copy rule:

```text
Claim only what PackageTruthGate proves.
Everything else is marked planned, experimental, or manual checklist.
```

### 7. Evidence location can become product behavior by accident

The memo proposes future `operations/release-evidence/...`. That is acceptable for repo-side release artifacts, but generated user cells should not inherit release evidence as runtime state. Release evidence belongs to maintainer operations, not the user's business cell.

Risk: if evidence schema migrates into product runtime too early, it can become a fake audit log before `RunAuthorityGate` exists.

## Hidden complexity inventory

| Area | Hidden failure mode | Simpler posture |
|---|---|---|
| First chat | One boolean hides package, UI, API, supervisor, Hermes, credential, and receipt layers | Record step-level assertions and `not_asserted` states. |
| Clean install | Release proof ignores reruns and existing directories | Market as empty-target create only until authority gates exist. |
| Credential path | First-chat pressure encourages host-secret imports | BYOK prompt only; host credentials detected-only. |
| UI parity | Loaded page may be stale copied bundle | Record build/package/asset digest or mark parity not asserted. |
| Negative tests | Denial names without side-effect proof | Negative evidence must assert no mutation. |
| Public copy | Multi-user shell language outruns single-user proof | Docs claims must be gated by evidence scope. |
| Evidence folder | Release artifact becomes confused with runtime audit | Keep release evidence operational, not product state. |

## Simpler first-principles alternative

Collapse the v0.1.x release proof into two artifacts, not one overloaded artifact:

```text
PackageInstallEvidence
  proves: packed artifact creates empty target and boots managed stack
  excludes: credentials, team mode, host runtime adoption

FirstRunEvidence
  proves: explicit BYOK credential path can produce one managed-Hermes chat and minimal receipt
  excludes: billing, delegation, host CLI sessions, non-Hermes adapters
```

Then `PackageTruthGate` becomes a decision over both artifacts:

```text
PackageTruthGate = PackageInstallEvidence.allow && FirstRunEvidence.allow && NegativeInstallEvidence.deny_cases_green
```

This is less elegant than one JSON file but harder to fake.

## Proposed migration / refactor steps

1. Split the proposed evidence schema into install evidence, first-run evidence, and negative-case evidence sections, even if stored in one JSON envelope.
2. Add explicit `asserted | not_asserted | failed` per step instead of booleans only.
3. Make `empty target only` a public release constraint until `CellAuthorityGate` supports open/update/connect/adopt.
4. Require negative tests to prove no mutation, not just deny decisions.
5. Require redacted credential source classification and prohibit host auth/config imports in release evidence.
6. Define UI/package parity as digest/build identity comparison; otherwise record parity as not asserted.
7. Add a docs-claim gate: README/install/release docs cannot claim branches outside the evidence scope.
8. Keep release evidence under operations/maintainer control and do not present it as product audit until `RunAuthorityGate` receipts exist.

## Diagnostic conclusion

The planning rail is converging correctly, but the current release gate still risks becoming a large green checkbox over several independent hazards. The safer next move is to make evidence granular, denial-oriented, and claim-limiting: prove empty-target package install, prove one explicit BYOK first run, prove unsafe paths do not mutate, and make public copy match only those proofs.

## Next best planning target

Final implementation-ticket backlog ranked by release blocker severity, with each ticket mapped to one evidence assertion or denial case rather than broad architecture themes.
