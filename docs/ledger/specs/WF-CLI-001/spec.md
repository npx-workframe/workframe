# WF-CLI-001 — First coherent Socratic slice

**Status:** todo  
**Scope:** `packages/workframe/**` only

## First-principles decision

The scheduled campaign mixed four separate problems into one change:

1. discovering installed runtimes and providers;
2. selecting and verifying a billable inference path;
3. conducting a Socratic conversation;
4. composing and deploying Architectonic and Workframe.

That produced an unmergeable branch, repeated ledger reconciliation, and authority bugs where mentioning a provider could be interpreted as selecting it.

The repository therefore returns to the last shipped coherent package, `workframe@0.2.1`. PRs #6, #7, and #9 are rejected implementation evidence, not source code to merge. Their useful tests and findings may inform a new implementation, but their branches are not continuation points.

## What remains true

The standalone CLI already provides a read-only local status console and one explicitly approved minimal link test. It must remain usable without installing, adopting, or changing Workframe, Architectonic, or any detected runtime.

The long-term sequence remains:

1. mirror the human and define an entity;
2. clarify purpose, goals, constraints, and success criteria;
3. produce a structured constitutional draft;
4. map that draft to Architectonic layers and agents;
5. reconcile with existing state without overwriting it;
6. produce a Workframe deployment plan;
7. apply only an immutable reviewed plan with explicit authority.

## Next implementation slice

Implement `workframe begin` as a deterministic, memory-only conversation with **no model or provider call**.

It should ask, one question at a time:

- what the human wants to be called;
- what entity, project, or organization they are defining;
- what they are trying to bring into existence or change;
- why that matters;
- what success would look like;
- which constraints or non-negotiables already exist.

It should then print and optionally emit as JSON a bounded first mirror containing:

- human;
- entity;
- stated purpose;
- goals;
- constraints;
- success criteria;
- unresolved questions;
- provenance for every field: `stated` or `unresolved`.

## Acceptance

- `workframe status` remains byte-for-byte behaviorally compatible with `0.2.1`.
- `workframe begin` performs no network call and reads no provider credential.
- The session remains memory-only; no file is written unless a later command receives separate explicit approval.
- EOF, Ctrl+C, timeout, refusal, and empty answers stop cleanly.
- User text is bounded, control characters are removed, and no answer is silently reinterpreted as a different fact.
- `--json` produces stable machine-readable output with no ANSI text.
- Tests use replayable scripted conversations on Node 20, 22, and 24 semantics.
- The packed npm bin passes `--version`, `status --json`, and scripted `begin --json` checks.

## Explicit non-goals

This slice does not:

- choose or call Codex, Claude, OpenAI, OpenRouter, Hermes, Pi, or any other runtime;
- use an LLM to interpret answers;
- write Architectonic files;
- run `create-workframe`;
- install, adopt, update, or deploy anything;
- publish a new npm version.

After this slice is accepted, model-assisted interpretation can be added behind a separate provider-neutral adapter and a separate consent boundary.