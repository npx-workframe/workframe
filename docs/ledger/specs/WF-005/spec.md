# WF-005 — Local release gates cannot be skipped silently

## Problem

`.harness/verify.mjs` skips `cursor-local` scenarios in CI. Release must not treat CI green as sign-off.

## Solution

- `verify.mjs` logs `[blocked-local]` for local scenarios not passing (CI still passes).
- `verify-release-gates.mjs` fails closed before npm publish:
  - **installer-ui-bundle** — `PackageInstallEvidence` with `ui_bundle_identity` or `feature_list.passes`
  - **dogfood-install-gate** — `feature_list.passes` after wizard + chat (WF-020 will automate later)
- `install-gate.ps1` emits package install evidence after pack.
- `publish-npm.ps1` invokes `verify-release-gates.mjs`.

## Verify

```bash
node scripts/workframe/verify-release-gates.mjs
pnpm verify:release-gates
```
