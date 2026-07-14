# WF-CLI-001 — Conversational link and memory-only Socratic seed

**Status:** review  
**Implementer:** `workframe-cli-builder`  
**Reviewer:** `workframe-cli-reviewer`

## Campaign boundary

This campaign changes only the standalone `packages/workframe` CLI. It must not modify `create-workframe`, Workframe services, apps, infrastructure, or an existing user installation.

The bounded progression is:

1. natural-language inference-path selection and explicit consent;
2. truthful capability graph for installed runtimes and configured providers;
3. provider-neutral model-assisted dialogue behind deterministic authority boundaries;
4. Socratic entity, identity, purpose, and goal discovery;
5. structured constitution, doctrine, identity, project, agent, and skill draft;
6. non-destructive reconciliation with existing Architectonic and Workframe state;
7. dry-run deployment plan with explicit mutation approval;
8. packed-package and cross-platform release evidence.

## Current slice

The CLI discovers existing inference paths, asks which path to use when several are available, discloses who pays, and requires a separate explicit approval before a minimal verification call. After the selected path is verified, `workframe begin` asks who is speaking and what they are trying to bring into existence, then prints a bounded first mirror.

The first mirror is deterministic and exists in memory only. It distinguishes the human's stated objective from unresolved purpose, constraints, and success criteria. It does not yet send the Socratic answers to a model, write Architectonic layers, or deploy Workframe.

## Acceptance

- One runtime/provider can be selected by id, label, supported alias, exclusion, or explicit delegation.
- Multiple positive runtime mentions remain ambiguous rather than being guessed.
- Runtime selection itself performs no network call and mutates no files.
- Provider verification remains bounded, read-only, billing-disclosed, and separately consent-gated.
- Negative intent takes precedence over positive words; polite but non-consenting language remains ambiguous.
- A verified `begin` flow collects preferred name and first objective, then prints a memory-only mirror.
- EOF, refusal, missing objective, and provider failure stop without persistence or installation mutation.
- Credential values never appear in status output.
- Package checks and packed npm-bin smoke checks pass without live credentials.

## Evidence

- `packages/workframe/bin/workframe.js`
- `packages/workframe/lib/dialogue.js`
- `packages/workframe/lib/session.js`
- `packages/workframe/checks/workframe-checks.js`
- `packages/workframe/package.json`
- Code commit: `1ce146fe1147af9c9f104626da2eee7043d559b1`
- `cd packages/workframe && npm test`: 12/12 passing.
- `npm pack --ignore-scripts` followed by a clean temporary install: passing.
- Installed npm-bin `workframe --version`: `0.2.1`.
- Installed npm-bin `workframe status --json`: valid JSON with credential values absent.
- POSIX npm-bin symlink invocation regression check: passing.

No package was published. No provider verification call was performed during implementation. No existing installation, runtime, credential, service, app, or infrastructure path was modified.
