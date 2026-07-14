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

## Previous independent review — rejected 2026-07-14

Reviewed head: `c15f250af9edf51650917a80fe928b880003150f`.

The first review identified invalid OpenRouter request syntax, consent that could authorize on questioning language, inaccurate credential wording, incomplete authority-boundary tests, and non-deterministic EOF/Ctrl+C behavior. The first four classes were repaired in implementation commit `e05bdb53f934d20a44b2fee4468f76805c337527`. Real PTY review then found that Ctrl+C could still end with an unsettled top-level await and Ctrl+D could be misclassified as timeout.

## Implementer remediation verified in the second review

Patch references:

- `e05bdb53f934d20a44b2fee4468f76805c337527` — syntax, consent, wording, injectable flow, and bounded-session repairs.
- `048aa413cd89ccb9f4bb348597a7087a04ef0d55` — callback readline terminal adapter with deterministic process/readline SIGINT, EOF, close, and timeout settlement.
- `57cfe7359c39584017552d906642e0c7bb3c1de5` — direct adapter tests for normal input, process SIGINT, readline SIGINT, timeout, EOF, and a real ended input stream.

On Linux x64 with Node `v22.16.0`, 26 package tests passed. A packed `workframe-0.2.1.tgz` installed cleanly, returned version `0.2.1`, and produced valid status JSON. Real pseudo-terminal Ctrl+C and Ctrl+D checks exited cleanly with the safe-stop message and no provider invocation.

## Second independent review — rejected 2026-07-14

Reviewed head: `c87166e935f31133ee42374e5d415669728db6e3`. Package contents were unchanged from `57cfe7359c39584017552d906642e0c7bb3c1de5`.

The reviewer found that runtime errors could expose credential values, CLI verification could false-positive on echoed prompt text, direct providers could false-positive on refusal text containing the verification token, and questions about the best/default runtime could silently select the first candidate. Repository CI also remained red at aggregate `Harness verify`.

## Current remediation candidate

Submitted head: `b4c7c6a278c56d5958f73a3fecd289f428cf11fb`.

The candidate is returned to independent review with these bounded changes:

- Runtime child environments now use an allowlist plus only the selected candidate's credential environment names.
- Known credential values are redacted from subprocess stdout, stderr, and errors before any diagnostic is displayed.
- Codex and Claude verification parses structured assistant result fields and requires the isolated response to equal `WORKFRAME_OK` exactly.
- OpenAI and OpenRouter verification parses provider JSON and requires the assistant response field to equal `WORKFRAME_OK` exactly.
- Questions containing `best`, `default`, `recommended`, or `first` remain unresolved unless the user uses an explicit imperative delegation phrase.
- Adversarial regressions cover secret-bearing stderr, argv echo, refusal text, and best/default questions.

CI run `29347827885` still fails at aggregate repository CI and is not acceptance evidence. The independent reviewer must rerun package-local, packed-artifact, pseudo-terminal, and available CI checks from the exact submitted head before moving this item to `done` or back to `todo`.

## Ledger reconciliation

`WF-CLI-001` is in `review`. The canonical `docs/ledger/backlog.json` contains one `WF-CLI-001`–`WF-CLI-008` campaign; `WF-CLI-002` remains dependency-gated. No live provider call was made. No package was published. No installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
