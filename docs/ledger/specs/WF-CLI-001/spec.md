# WF-CLI-001 — Conversational inference-path selection

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
- Node tests and package smoke checks pass.
