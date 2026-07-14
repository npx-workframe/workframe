# WF-CLI-001 — Conversational link and memory-only Socratic seed

**Status:** todo  
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

The CLI discovers existing inference paths, asks which path to use when several are available, discloses who pays, and requires separate explicit approval before a minimal verification call. After the selected path is verified, `workframe begin` asks who is speaking and what they are trying to bring into existence, then prints a bounded first mirror.

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

## Review result — rejected 2026-07-14

Reviewed head: `c15f250af9edf51650917a80fe928b880003150f`.

WF-CLI-001 is returned to `todo` for these blocking failures:

1. `packages/workframe/bin/workframe.js` contains `body: JSON.stringify {` in `testOpenRouter`. This is invalid JavaScript, so `npm run check` and `npm test` cannot pass on the reviewed head. The PR's recorded 12/12 evidence therefore does not describe the current head.
2. `interpretConsent` treats `sure` and `okay` as affirmative tokens wherever they appear. `Sure, what will this cost?` and `Okay, explain what will be sent first.` both resolve to `yes`, allowing a question or request for explanation to authorize a provider call.
3. Help text states that credential values are never transmitted by Workframe. Direct OpenAI and OpenRouter verification sends the selected environment credential to that provider after consent. The truthful claim is that credentials are never printed or persisted and are transmitted only to the explicitly approved provider.
4. The package checks cover parser helpers and entrypoint smoke tests, but not the actual authority boundary. Tests must prove that denial and ambiguous consent prevent invocation, failed verification prevents the Socratic prompts, and identity/objective questions occur only after a verified link.
5. `runInteractive` no longer catches input termination. EOF before explicit approval exits non-cleanly rather than producing the required safe stop result. Ctrl+C, timeout, and closed-input behavior also need deterministic tests.
6. The current CI run fails at `Harness verify`. The harness failure may be repository baseline, but it cannot be used as green evidence, and CI does not currently execute the standalone package checks that would catch the syntax defect.

## Required remediation

- Restore valid `JSON.stringify({...})` syntax and rerun package-local and packed-artifact checks from the exact new head.
- Make affirmative consent fail closed for questions, conditions, qualifiers, requests for explanation, and other ambiguous language. Negative language must continue to win.
- Correct all credential wording to distinguish no printing/persistence from approved transmission to the selected provider.
- Add injectable verification and dialogue seams with end-to-end tests for denial, ambiguity, invocation count, failed verification, missing objective, EOF, Ctrl+C, and timeout.
- Reconcile the canonical `WF-CLI-001` row in `docs/ledger/backlog.json` from `review` to `todo`, preserving every existing non-CLI row and ledger history.

## Evidence reviewed

- `packages/workframe/bin/workframe.js`
- `packages/workframe/lib/dialogue.js`
- `packages/workframe/lib/session.js`
- `packages/workframe/checks/workframe-checks.js`
- `packages/workframe/package.json`
- PR #7 head `c15f250af9edf51650917a80fe928b880003150f`
- CI run `29333673842`: failed at `Harness verify`
- Static syntax reproduction: `node --check` rejects `JSON.stringify {` with `SyntaxError: Unexpected token '{'`
- Consent reproduction: `Sure, what will this cost? => yes`
- Consent reproduction: `Okay, explain what will be sent first. => yes`
- EOF reproduction: a pending `readline/promises.question` with closed stdin exits non-cleanly without an explicit catch

## Ledger reconciliation

The campaign staging record is now `todo` with exact failure evidence. The large machine queue still needs a safe fresh-head replacement of only the WF-CLI-001 status/workflow fields; it was not rewritten during this review because the available contents write is whole-file replacement and must not risk clobbering unrelated ledger history.

No package was published. No live provider call was made. No existing installation, runtime, credential, service, app, or infrastructure path was modified.
