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

- One runtime/provider can be selected by id, label, supported alias, exclusion, or explicit imperative delegation.
- Multiple positive runtime mentions, questions, hedged answers, and non-imperative best/default language remain unresolved rather than being guessed.
- Runtime selection itself performs no network call and mutates no files.
- Provider verification remains bounded, read-only, billing-disclosed, cancellable, and separately consent-gated.
- Runtime children receive a minimal inference-only environment plus only the credential explicitly selected for that candidate.
- Credential values are redacted from subprocess and provider diagnostics before display.
- Codex, Claude, OpenAI, and OpenRouter verification requires an exact assistant response from a structured response field; prompt echoes, refusal text, and diagnostic text cannot verify a link.
- Negative intent takes precedence over positive words; polite, conditional, questioning, or explanatory language remains non-authorizing.
- A verified `begin` flow collects preferred name and first objective, then prints a memory-only mirror.
- EOF, Ctrl+C, timeout, refusal, missing objective, and provider failure stop promptly without persistence or installation mutation.
- Package checks and packed npm-bin smoke checks pass without live credentials.

## Review history

The first independent review rejected invalid OpenRouter request syntax, fail-open consent language, inaccurate credential wording, incomplete authority tests, and non-deterministic terminal interruption behavior.

The second independent review rejected credential-bearing subprocess diagnostics, prompt-echo and refusal-text false positives, and implicit best/default selection.

The submitted hardening repairs structured response parsing, known environment-secret redaction, consent fail-closed behavior, and question-form best/default handling. Those repairs are retained, but the slice remains rejected.

## Third independent review — rejected 2026-07-14

Reviewed implementation head: `2b85c70d3fb9302dc435c45459ac698ca46a05f6`.

Verified by source inspection and targeted exact-parser reproduction:

- structured assistant/provider response fields require exact `WORKFRAME_OK`;
- configured secret-like environment values are redacted from displayed subprocess diagnostics;
- questioning best/default answers remain unresolved;
- questioning and qualified consent remains non-authorizing;
- consent-prompt EOF and Ctrl+C settlement paths are present.

Blocking findings:

1. **Ctrl+C does not cancel a verification already in flight.** `runInteractiveFlow` awaits `verify(candidate)` without a cancellation signal. HTTP verification uses only a 30-second timeout signal, while Codex and Claude use synchronous `spawnSync` with a 90-second timeout. The terminal SIGINT handler can close readline, but it cannot abort the provider request or child process. A user can therefore press Ctrl+C after consent and still wait for, and potentially be billed for, the request.
2. **Hedged runtime answers are treated as selections.** The exact current parser selects `Maybe Claude.`, `Probably Codex.`, `Claude, perhaps.`, and `I guess OpenRouter.` because a single candidate mention is accepted before uncertainty is evaluated.
3. **Runtime billing is not deterministic.** If Codex or Claude is available and a corresponding API key is also configured, the candidate receives that key automatically while the disclosure says the call may use either the existing account or the configured provider. The exact credential and payer are not selected or stated.
4. **The inference environment contains unrelated authority handles.** `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_CONFIG`, and `SSH_AUTH_SOCK` are included in the shared child allowlist even though they are not required for a model verification call.
5. **The candidate is not merge-ready.** The PR branch is diverged, eighteen commits ahead and nine commits behind current `main`, and GitHub reports it as unmergeable. The exact reviewed head has no attached package or repository CI run.

## Required remediation

- Thread one cancellation signal from terminal handling through the interactive flow into verification.
- Abort OpenAI/OpenRouter fetches and replace synchronous Codex/Claude execution with a cancellable child process that is terminated on Ctrl+C.
- Add real verification-phase interruption tests, not only consent-prompt PTY tests.
- Treat uncertainty markers such as `maybe`, `perhaps`, `probably`, and `I guess` as unresolved candidate selection.
- Represent account-backed and API-key-backed paths separately, and disclose the exact payer and credential source before consent.
- Split discovery and inference environment allowlists; remove Docker and SSH handles from inference children.
- Rebase onto current `main`, reconcile the canonical `docs/ledger/backlog.json` WF-CLI-001 row to `todo`, and rerun package-local, packed-artifact, PTY, Windows semantics, and available CI checks from the exact repaired head.

## Ledger reconciliation

The campaign staging record now returns `WF-CLI-001` to `todo`; `WF-CLI-002` and later items remain dependency-gated. Current `main` still contains a stale `review` row with PR #6 evidence, so a narrow canonical reconciliation remains required. The full queue was not replaced during review because doing so through the connector would risk overwriting unrelated ledger history.

`now.md` was not updated. No live provider was called, no package was published, and no installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
