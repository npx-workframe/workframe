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

The CLI discovers existing inference paths, represents account-backed and direct API-key paths separately, asks which path to use when several are available, and discloses the payer, credential source, and invocation before separate explicit approval of one minimal verification call.

The verification is intended to be cancellable through the terminal, HTTP request, and runtime-child boundaries. Runtime children receive a reduced inference environment without Docker, SSH, unrelated credentials, or arbitrary ambient variables. Only after the selected path is verified does `workframe begin` ask who is speaking and what they are trying to bring into existence, then print a bounded memory-only first mirror.

The first mirror distinguishes the human's stated objective from unresolved purpose, constraints, and success criteria. It does not send the Socratic answers to a model, write Architectonic layers, install packages, adopt an existing runtime, or deploy Workframe.

## Acceptance

- One runtime/provider can be selected by id, label, supported alias, exclusion, or explicit imperative delegation.
- Multiple positive runtime mentions, questions, hedged answers, descriptive mentions, negative-context mentions, and non-imperative best/default language remain unresolved rather than being guessed.
- Runtime selection itself performs no network call and mutates no files.
- Account-backed and API-key-backed paths are distinct candidates with exact payer, credential source, and invocation disclosure.
- Provider verification remains bounded, read-only, separately consent-gated, and cancellable.
- Runtime children receive a minimal inference-only environment plus only the credential explicitly selected for that candidate.
- Credential values are redacted from subprocess and provider diagnostics before display.
- Codex, Claude, OpenAI, and OpenRouter verification requires an exact assistant response from a structured response field; prompt echoes, refusal text, and diagnostic text cannot verify a link.
- Negative intent takes precedence over positive words; polite, conditional, questioning, explanatory, or uncertain language remains non-authorizing.
- A verified `begin` flow collects preferred name and first objective, then prints a memory-only mirror.
- EOF, Ctrl+C, timeout, refusal, missing objective, and provider failure stop promptly without persistence or installation mutation.
- Package-local, real-PTY, Windows-semantics, exact-head CI, and packed npm-bin checks pass without live credentials.

## Review history

The first independent review rejected invalid OpenRouter request syntax, fail-open consent language, inaccurate credential wording, incomplete authority tests, and non-deterministic terminal interruption behavior.

The second independent review rejected credential-bearing subprocess diagnostics, prompt-echo and refusal-text false positives, and implicit best/default selection.

The third independent review of `2b85c70d3fb9302dc435c45459ac698ca46a05f6` verified structured response parsing, known-secret redaction, consent fail-closed behavior, and consent-prompt interruption, but rejected the slice because verification itself was not cancellable, hedged selections were accepted, account and API-key billing paths were conflated, inference children inherited Docker and SSH handles, and the branch was diverged without exact-head CI evidence.

## Fourth independent review

Reviewed pull request: `#9`  
Reviewed final head: `a62ce6d30723ce7f6a0d4aeab7a46615cf41db41`  
Package implementation head: `3c1b64a49eb25f09c0a8da448f5bfb355394d88a`  
Result: **rejected; return to todo**

Verified repairs:

- the branch was rebuilt from then-current `main` and was mergeable;
- cancellation was threaded through the terminal, HTTP request, and asynchronous child-process interfaces;
- account-backed and direct API-key candidates were separate;
- inference child environments excluded Docker, SSH, unrelated credentials, and arbitrary ambient variables;
- structured provider parsers required the exact `WORKFRAME_OK` assistant response.

Blocking findings:

1. **Candidate mentions authorized a path without affirmative selection.** Exact reproductions included `I don't know anything about Claude.`, `I don't trust OpenRouter.`, `Claude is installed.`, and `Claude sounds risky.`.
2. **Exclusions could select an unrelated provider.** `Don't use Claude; use Codex.` and `Not Claude, use Codex.` resolved to the sole unmentioned OpenRouter candidate.
3. **Windows cancellation was not proven fail-closed.** Production started `taskkill` detached and unrefed without observing spawn error, exit code, or completion, while the test bypassed that path with an injected terminator.
4. **Exact-head CI was red.** CI failed at `Harness verify`, skipped downstream package evidence, and did not independently run the package-local and packed-tarball matrix.

Rejected PR #9 is closed unmerged and retained only as evidence. Its exact failure phrases remain mandatory regressions for every later implementation.

## Active candidate awaiting reconciliation

Sole active pull request: `#7`  
Current pull-request head: `82a18716e6c758762916657f6577d78290f7b779`  
Implementation head: `6a820c3b970f59dc51d484cbb457de65819f3a7a`  
Result: **not yet eligible for independent review**

The candidate reports:

- 43 package tests passed before the focused eligibility patch;
- a packed `workframe-0.2.1.tgz` installed cleanly and its npm bin returned valid version and status output before the focused patch;
- installed-only Claude discovery no longer creates an authenticated account-backed candidate;
- explicitly authenticated Claude and `ANTHROPIC_API_KEY` paths remain separate;
- cancellation, inference environment isolation, payer disclosure, hedged-selection denial, and structured response verification are covered by focused tests.

These are implementer-submitted claims, not acceptance. The branch must first reconcile the CLI-specific current-main ledger commits without replacing unrelated queue history. Only then may `WF-CLI-001` return to review. Independent review must use one exact reconciled head and verify:

1. the complete package suite, including `candidate-eligibility.test.js`;
2. installed-only Claude cannot be selected or billed as an authenticated account path;
3. authenticated-account and API-key-backed Claude paths remain distinct with exact payer disclosure;
4. all fourth-review descriptive, negative-context, and mixed-exclusion phrases remain unresolved or select only the explicit affirmative clause;
5. production Windows `.cmd` cancellation awaits and validates `taskkill` completion rather than using an injected terminator;
6. Ctrl+C promptly terminates HTTP and child verification and prevents every Socratic prompt;
7. packed-artifact, PTY, Windows-semantics, and available repository CI evidence all correspond to the same exact head.

## Evidence boundary

Current exact-head repository CI run `29356756330` is red at `Harness verify`; downstream package-install and negative-install steps were skipped. This is not acceptance evidence. `WF-CLI-002` remains dependency-gated. `now.md` is unchanged because this slice has not been accepted or shipped. No live provider was called, no package was published, and no installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
