# WF-CLI-001 — Conversational inference-path selection

**Status:** review  
**Implementer:** `workframe-cli-builder`  
**Reviewer:** `workframe-cli-reviewer`

## Campaign boundary

This campaign changes only the standalone `packages/workframe` CLI. It must not modify `create-workframe`, Workframe services, apps, infrastructure, or an existing user installation.

The bounded progression is:

1. natural-language inference-path selection and explicit consent;
2. truthful capability graph for installed runtimes and configured providers;
3. verified inference session with a deterministic transport boundary;
4. Socratic entity, identity, purpose, and goal discovery;
5. structured constitution, doctrine, identity, project, agent, and skill draft;
6. non-destructive reconciliation with existing Architectonic and Workframe state;
7. dry-run deployment plan with explicit mutation approval;
8. packed-package and cross-platform release evidence.

## Current slice

When more than one safe inference path is available, the CLI asks the user which path to use in natural language. It must resolve one explicit choice, honor exclusions, reject ambiguous multi-choice answers, disclose the billing source, and make no provider call until a separate explicit consent step succeeds.

## Acceptance

- Natural affirmative and negative consent are interpreted deterministically, with negative intent taking precedence.
- One runtime/provider can be selected by id, label, or supported alias.
- Multiple positive runtime mentions remain ambiguous rather than being guessed.
- Exclusions such as “anything except Claude” are honored.
- Deterministic ranking is used only when the user delegates the choice.
- Selection itself performs no network call and mutates no files.
- Existing provider-test behavior remains bounded, read-only, and consent-gated.
- Polite but non-consenting responses remain ambiguous and cannot trigger a provider call.
- Node tests and package smoke checks pass.

## Evidence

- `packages/workframe/lib/dialogue.js`
- `packages/workframe/test/dialogue.test.js`
- `packages/workframe/bin/workframe.js`
- `packages/workframe/package.json`
- Commits: `1f30820`, `17fd9bd`, `aa39814`, `ac62f1c`, `0011730`, `9b2926e`
- `npm test`: 7/7 passing, including negative precedence, ambiguous consent, multiple candidate names, and exclusions.
- `npm pack --dry-run --json`: packed artifact contains `bin/workframe.js`, `lib/dialogue.js`, and `package.json`.

## Integrator reconciliation

The bounded campaign manifest is preserved at `campaign.json` on main. `WF-CLI-001` remains in review and `WF-CLI-002` remains blocked until independent review closes the first slice.

The open PR's candidate `backlog.json` must not be merged as-is because it also rewrites unrelated existing wave assignments. Machine-queue reconciliation must append only `WF-CLI-001` through `WF-CLI-008` to a fresh current-main `backlog.json`, preserving all pre-existing ledger rows otherwise.

No package was published. No existing installation, runtime, credential, service, app, or infrastructure path was modified.
