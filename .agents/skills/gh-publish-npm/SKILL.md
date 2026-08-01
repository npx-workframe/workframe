---
name: gh-publish-npm
description: Understand, audit, prepare, or safely execute the Workframe GitHub Actions to npm publishing workflow. Use when working on .github/workflows/publish-npm.yml, release tags, npm trusted publishing/OIDC, package version bumps, npm publication, registry verification, or the local publish fallback in scripts/workframe.
---

# Workframe GitHub-to-npm publishing

## Overview

Use repository source as truth. Trace the workflow before changing release instructions, and distinguish the two independently published packages: `create-workframe` and `workframe`.

## Source map

Read these files before answering a workflow or release question:

- `.github/workflows/publish-npm.yml` - authoritative CI behavior.
- `docs/public/release.md` - setup and maintainer guidance; verify it against the workflow because it can drift.
- `scripts/workframe/publish-npm.ps1` - local OTP/token fallback, stricter than CI in some respects.
- `scripts/workframe/verify-release-gates.mjs` - local evidence gates.
- `packages/create-workframe/package.json` and `packages/workframe/package.json` - package names and versions.

## Trigger matrix

| Event | `create-workframe` job | `workframe` job |
|---|---:|---:|
| Push to `main` | No | Yes, only when `packages/workframe/**` or the workflow changes |
| Push tag `vX.Y.Z` | Yes | Yes |
| Manual `workflow_dispatch` | Yes | Yes |

Do not assume a `main` push publishes `create-workframe`; it is tag/manual-only. Pull requests do not trigger this workflow.

## CI workflow

For `create-workframe` on a tag, require the package version to exactly equal the tag version. The job then:

- Requires GitHub secret `VERIFY_PUBLIC_PATTERNS_JSON` and writes it to the gitignored local denylist file.
- Installs with pnpm using the frozen lockfile.
- Runs strict public-repo verification, API Python compilation, web build, UI bundling, and scaffold smoke tests.
- Upgrades npm because trusted publishing requires a recent npm CLI.
- Publishes from `packages/create-workframe` using `npm publish --access public`.
- On tags, polls npm for the tagged version for up to twelve attempts.

For `workframe`, the job:

- Runs `npm test` in `packages/workframe`.
- Compares its package version with `npm view workframe version`.
- Skips publication when that exact version is already in the registry; otherwise publishes with `npm publish --access public`.
- Polls npm afterward and fails if the expected version does not appear.

Both jobs use npm trusted publishing/OIDC. The workflow grants `id-token: write` and does not use an `NPM_TOKEN`.

## Release procedure

1. Inspect current package versions, workflow conditions, Git status, and existing tags.
2. Complete the canonical sync/build/evidence gates appropriate to the code changed. UI changes require a web build and installer UI bundling; API/supervisor changes require canonical package sync.
3. Bump the package version(s) intended for publication and update version-agreement artifacts if the repository requires them.
4. Commit the release changes.
5. For `create-workframe`, create a matching tag and push both `main` and the tag:

   ```bash
   git push origin main
   git push origin vX.Y.Z
   ```

6. Watch the GitHub Actions run and verify the npm registry version. Do not claim publication from a green commit alone.

Before relying on OIDC, verify npm trusted publishing is configured for each package with repository `npx-workframe/workframe` and workflow filename `publish-npm.yml`. Confirm the GitHub secret required by the create job exists.

## Local fallback

Use `.\scripts\workframe\publish-npm.ps1` only when local publication is explicitly requested or CI is unavailable. It checks the public-repo denylist, runs `verify-release-gates.mjs`, requires `npm whoami`, and publishes `create-workframe`. It is not a substitute for the GitHub OIDC path and does not publish the standalone `workframe` package.

Treat missing or stale `PackageInstallEvidence`, `FirstRunEvidence`, and `NegativeInstallEvidence` as release blockers for the local path. Never bypass a failed gate by editing evidence to claim success.

## Known drift checks

Call out, rather than silently "fix," any mismatch between docs and code. The current tree's release doc mentions `@workframe/workframe`, while the workflow publishes only `create-workframe` and `workframe`; its sample tag may also be historical. Confirm package discovery and workflow behavior from source before updating guidance.
