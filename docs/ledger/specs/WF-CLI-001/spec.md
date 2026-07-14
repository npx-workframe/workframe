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

The CLI discovers existing inference paths, represents account-backed and direct API-key paths separately, asks which path to use when several are available, and discloses the exact payer, credential source, and invocation before separate explicit approval of one minimal verification call.

The verification is cancellable through the terminal, HTTP request, and runtime-child boundaries. Runtime children receive a minimal inference environment without Docker, SSH, unrelated credentials, or other ambient authority handles. Only after the selected path is verified does `workframe begin` ask who is speaking and what they are trying to bring into existence, then print a bounded memory-only first mirror.

The first mirror distinguishes the human's stated objective from unresolved purpose, constraints, and success criteria. It does not send the Socratic answers to a model, write Architectonic layers, install packages, adopt an existing runtime, or deploy Workframe.

## Acceptance

- One runtime/provider can be selected by id, label, supported alias, exclusion, or explicit imperative delegation.
- Multiple positive runtime mentions, questions, hedged answers, and non-imperative best/default language remain unresolved rather than being guessed.
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

## Remediation submitted for independent review

Implementation branch: `automation/wf-cli-001-cancellable-link-v5`  
Base: `1d2c9a6cae56b347faf04f36e6083378a98eeae2`  
Pull request: `#9`  
Submitted head before ledger-only commits: `3c1b64a49eb25f09c0a8da448f5bfb355394d88a`

Implemented repairs:

- terminal cancellation is threaded into `runInteractiveFlow`, HTTP verification, and asynchronous runtime child execution;
- an interrupted or timed-out runtime child is terminated and cannot advance to Socratic prompts;
- `maybe`, `perhaps`, `probably`, `I guess`, questions, and non-imperative recommendations remain unresolved;
- Codex and Claude account sessions are separate from direct OpenAI and OpenRouter API-key candidates;
- each candidate states one exact payer, credential source, and invocation before consent;
- inference environments exclude Docker, SSH, unrelated credentials, and arbitrary ambient variables;
- exact structured assistant responses are required;
- the stale monolithic dialogue test was replaced with focused dialogue, authority, verification, terminal, package, and cancellation suites.

Exact-head local evidence before ledger-only commits:

- `cd packages/workframe && npm test`: 18/18 passed on Linux x64 / Node v22.16.0;
- `npm pack` produced `workframe-0.2.1.tgz`;
- a clean temporary install returned version `0.2.1` and valid `status --json`;
- a real PTY synthetic verification proved Ctrl+C after consent aborts the in-flight verification, returns `stopped:interrupt`, and emits no Socratic prompt;
- no live provider call, package publication, installation mutation, or non-CLI code change occurred.

## Independent review focus

- rerun package tests and packed install from the final PR #9 head;
- inspect Windows npm-script, `.cmd`, quoting, and child termination semantics;
- verify HTTP and runtime-child cancellation promptly prevents Socratic prompts;
- verify exact payer and selected-credential disclosure for every candidate;
- inspect pull-request CI and classify any repository-baseline harness failure separately from package evidence.

## Ledger boundary

`WF-CLI-002` remains dependency-gated. `now.md` is unchanged because this slice has not been accepted or shipped. No live provider was called, no package was published, and no installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
