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

The CLI discovers existing inference paths, asks which path to use when several are available, discloses who pays, and requires separate explicit approval before a minimal verification call. After the selected path is verified, `workframe begin` asks who is speaking and what they are trying to bring into existence, then prints a bounded first mirror.

The first mirror is deterministic and exists in memory only. It distinguishes the human's stated objective from unresolved purpose, constraints, and success criteria. It does not yet send the Socratic answers to a model, write Architectonic layers, or deploy Workframe.

## Acceptance

- One runtime/provider can be selected by id, label, supported alias, exclusion, or explicit delegation.
- Multiple positive runtime mentions remain ambiguous rather than being guessed.
- Runtime selection itself performs no network call and mutates no files.
- Provider verification remains bounded, read-only, billing-disclosed, and separately consent-gated.
- Negative intent takes precedence over positive words; polite, conditional, questioning, or explanatory language remains non-authorizing.
- A verified `begin` flow collects preferred name and first objective, then prints a memory-only mirror.
- EOF, Ctrl+C, timeout, refusal, missing objective, and provider failure stop without persistence or installation mutation.
- Credential values never appear in any CLI output.
- Package checks and packed npm-bin smoke checks pass without live credentials.

## Previous independent reviews — rejected 2026-07-14

The first review of `c15f250af9edf51650917a80fe928b880003150f` identified invalid OpenRouter request syntax, consent that could authorize on questioning language, inaccurate credential wording, incomplete authority-boundary tests, and non-deterministic EOF/Ctrl+C behavior.

The second review of `c87166e935f31133ee42374e5d415669728db6e3` verified the syntax, consent, wording, packed-package, and terminal-interruption repairs, then found separate blockers: credential-bearing runtime diagnostics, prompt-echo verification false positives, raw-response verification false positives, and best/default questions being interpreted as delegation. Repository CI also remained red at aggregate `Harness verify`.

## Current verification-hardening candidate

Review candidate: `eb8f81f0d4a92834d76c8a53f5e136cff3ed0c1a`.

The candidate claims these bounded repairs:

- Runtime child environments use an allowlist plus only the selected candidate's credential environment names.
- Known credential values are redacted from subprocess stdout, stderr, and errors before a diagnostic is displayed.
- Codex and Claude verification consumes structured assistant output and requires the isolated response to equal `WORKFRAME_OK` exactly.
- OpenAI and OpenRouter verification parses provider JSON and requires the assistant response field to equal `WORKFRAME_OK` exactly.
- Questions about the best, default, recommended, or first option remain unresolved unless the user uses an explicit imperative delegation phrase.
- Adversarial regressions cover secret-bearing stderr, argv echo, refusal or diagnostic text, and runtime-selection questions.

Implementer evidence records 34 passing package tests on Linux x64 / Node `v22.16.0`, a packed `workframe-0.2.1.tgz` with SHA-1 `858b1efb672ee673ddc4e9d6a079aa6e7ee765c5`, a clean temporary install, and clean real-PTY Ctrl+C/Ctrl+D stops. CI run `29348238879` passed dependency installation, version agreement, docs-claim, and evidence steps, then failed at aggregate `Harness verify`; it is not acceptance evidence.

## Independent review gate

The reviewer must independently reconstruct the exact current package and:

1. rerun all 34 package tests;
2. prove configured credentials cannot escape through subprocess or provider diagnostics;
3. prove argv echo and non-assistant output cannot verify Codex or Claude;
4. prove refusal or diagnostic text cannot verify OpenAI or OpenRouter;
5. prove best/default questions remain unresolved without imperative delegation;
6. rerun packed-artifact, pseudo-terminal, and available CI checks.

`WF-CLI-001` remains in `review`; it is not accepted. `WF-CLI-002` remains dependency-gated.

## Ledger reconciliation

The canonical `docs/ledger/backlog.json` contains exactly one `WF-CLI-001`–`WF-CLI-008` campaign. `WF-CLI-001` is in `review`, and later slices remain dependency-gated. No live provider call was made. No package was published. No installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
