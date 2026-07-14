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

The CLI discovers existing inference paths, asks which path to use when several are available, and requires separate explicit approval before a minimal verification call. Account-backed and API-key-backed runtime paths are separate candidates, so the CLI can state the exact payer and credential source before consent.

After the selected path is verified, `workframe begin` asks who is speaking and what they are trying to bring into existence, then prints a bounded first mirror. The mirror exists in memory only. It distinguishes the human's stated objective from unresolved purpose, constraints, and success criteria. It does not yet send Socratic answers to a model, write Architectonic layers, or deploy Workframe.

## Acceptance

- One runtime/provider can be selected by id, label, supported alias, exclusion, or explicit imperative delegation.
- Multiple positive runtime mentions, questions, hedged answers, and non-imperative best/default language remain unresolved rather than being guessed.
- Runtime selection itself performs no network call and mutates no files.
- Provider verification remains bounded, read-only, billing-disclosed, cancellable, and separately consent-gated.
- Account-backed runtime paths receive no provider API key.
- API-key-backed paths receive only the explicitly selected credential.
- Inference children do not inherit Docker or SSH authority handles.
- Credential values are redacted from subprocess and provider diagnostics before display.
- Codex, Claude, OpenAI, and OpenRouter verification requires an exact assistant response from a structured response field; prompt echoes, refusal text, and diagnostic text cannot verify a link.
- Negative intent takes precedence over positive words; polite, conditional, questioning, hedged, or explanatory language remains non-authorizing.
- Ctrl+C and EOF propagate through one terminal lifecycle signal, cancel an in-flight HTTP request or runtime child, and prevent subsequent Socratic prompts.
- A verified `begin` flow collects preferred name and first objective, then prints a memory-only mirror.
- EOF, Ctrl+C, timeout, refusal, missing objective, and provider failure stop without persistence or installation mutation.
- Package checks and packed npm-bin smoke checks pass without live credentials.

## Implemented remediation

The third independent review rejected the previous candidate because verification could continue after Ctrl+C, hedged runtime answers were accepted, account and API-key billing paths were conflated, inference children inherited Docker/SSH authority, and the branch/evidence was stale.

The current candidate repairs those findings:

1. `createTerminalDialogue` owns an `AbortController`; process/readline SIGINT, EOF, and question timeout settle pending input and abort the same lifecycle.
2. `runInteractiveFlow` passes that signal into verification and stops before identity/objective prompts when verification is interrupted.
3. OpenAI and OpenRouter requests combine bounded timeout with the external cancellation signal.
4. Codex and Claude use asynchronous child processes that receive SIGTERM on cancellation and SIGKILL after a bounded grace period.
5. Candidate parsing rejects `maybe`, `perhaps`, `possibly`, `probably`, `I guess`, `I think`, `not sure`, and `unsure` language.
6. Codex and Claude expose separate account-backed and API-key-backed candidates with exact billing and credential disclosure.
7. Discovery and inference use distinct environment allowlists; inference excludes `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_CONFIG`, and `SSH_AUTH_SOCK`.
8. Tests cover exact structured verification, secret redaction, prompt-echo rejection, hedged choice rejection, billing-path separation, HTTP cancellation, real child termination, terminal cancellation, packed-bin semantics, and memory-only flow behavior.

## Verification recorded by implementer

Exact implementation head before ledger synchronization: `a3895f3c3cb6e2c13cdc205adb18f3b78bddf24c`.

- Linux x64, Node `v22.16.0`: `cd packages/workframe && npm test` — **43 passed**.
- `npm pack --json --ignore-scripts` produced `workframe-0.2.1.tgz` with shasum `9d6bc3538e0148faac54e490266a38ca33963c86`.
- A clean temporary install from that tarball returned `0.2.1` through the npm bin and valid `status --json` output.
- No live provider was invoked during testing.
- No package was published.
- No user installation, runtime, service, app, infrastructure path, or non-CLI product surface was changed.

## Independent review focus

The reviewer must verify the exact reconciled pull-request head, not the earlier implementation-only commit:

- rerun all package tests;
- interrupt a pending HTTP verification and a pending Codex/Claude child and confirm prompt flow stops immediately;
- confirm hedged selection remains unresolved;
- confirm account-backed candidates receive no provider keys and key-backed candidates receive only the selected key;
- confirm inference children cannot inherit Docker or SSH authority handles;
- run packed-artifact, npm-bin, Windows command semantics, and available repository CI checks;
- accept or return the item to `todo` with reproducible evidence.

## Ledger state

`WF-CLI-001` is submitted for independent review. `WF-CLI-002` remains dependency-gated. `now.md` remains unchanged until a reviewer accepts a shipping capability.
