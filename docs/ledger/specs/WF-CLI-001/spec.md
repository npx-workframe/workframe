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
- Negative intent takes precedence over positive words; polite, conditional, questioning, or explanatory language remains non-authorizing.
- A verified `begin` flow collects preferred name and first objective, then prints a memory-only mirror.
- EOF, Ctrl+C, timeout, refusal, missing objective, and provider failure stop without persistence or installation mutation.
- Credential values never appear in any CLI output.
- Package checks and packed npm-bin smoke checks pass without live credentials.

## Previous independent review — rejected 2026-07-14

Reviewed head: `c15f250af9edf51650917a80fe928b880003150f`.

The first review identified invalid OpenRouter request syntax, consent that could authorize on questioning language, inaccurate credential wording, incomplete authority-boundary tests, and non-deterministic EOF/Ctrl+C behavior. The first four classes were repaired in implementation commit `e05bdb53f934d20a44b2fee4468f76805c337527`. Real PTY review then found that Ctrl+C could still end with an unsettled top-level await and Ctrl+D could be misclassified as timeout.

## Implementer remediation verified in this review

Patch references:

- `e05bdb53f934d20a44b2fee4468f76805c337527` — syntax, consent, wording, injectable flow, and bounded-session repairs.
- `048aa413cd89ccb9f4bb348597a7087a04ef0d55` — callback readline terminal adapter with deterministic process/readline SIGINT, EOF, close, and timeout settlement.
- `57cfe7359c39584017552d906642e0c7bb3c1de5` — direct adapter tests for normal input, process SIGINT, readline SIGINT, timeout, EOF, and a real ended input stream.

The exact reviewed package files were reconstructed and their Git blob hashes matched the PR. On Linux x64 with Node `v22.16.0`:

```text
cd packages/workframe && npm test
26 tests passed; 0 failed
```

Packed-package proof also passed:

```text
npm pack --json --ignore-scripts
workframe-0.2.1.tgz
```

A clean temporary packed install returned version `0.2.1` and valid status JSON. Real pseudo-terminal Ctrl+C and Ctrl+D checks exited cleanly with the safe-stop message and no provider invocation.

## Independent review — rejected 2026-07-14

Reviewed head: `c87166e935f31133ee42374e5d415669728db6e3`. Package contents are unchanged from `57cfe7359c39584017552d906642e0c7bb3c1de5`; the later commits modify only this campaign's ledger documentation.

WF-CLI-001 is returned to `todo` for these blocking failures:

1. **Credential values can leak through runtime failure output.** Codex and Claude child processes inherit the full `process.env`. On failure, the CLI prints the first line of child `stderr` without redacting known credential values. A fake Codex executable that printed `OPENAI_API_KEY` to stderr caused the exact synthetic secret to appear in Workframe output, immediately after the CLI claimed credentials are never printed.
2. **CLI runtime verification can succeed without inference.** Codex and Claude verification scans combined stdout and stderr for `WORKFRAME_OK`, while the command-line prompt itself contains that token. Fake executables that only echoed their argv and exited zero were reported as verified links.
3. **Direct provider verification can accept a refusal as success.** OpenAI and OpenRouter adapters search the entire raw HTTP response body for `WORKFRAME_OK`. Synthetic HTTP 200 responses whose assistant text said `I refuse to output WORKFRAME_OK.` were accepted as verified.
4. **Questions can silently select the first runtime.** `interpretCandidateChoice` treats any normalized answer containing `best`, `default`, `recommended`, or `first` as delegation. `Which one is best?` and `What is the default?` both selected the first candidate rather than remaining unresolved.
5. **Repository CI is not green.** CI run `29345020181` failed at the aggregate `Harness verify` step. The independently executed package suite is green, but the repository workflow does not provide accepted end-to-end evidence for this head.

These findings violate the credential-safety, truthful-verification, and explicit-selection acceptance boundaries. They are separate from the repaired interruption behavior.

## Required remediation

- Redact configured credential values from all subprocess and provider diagnostics before printing. Prefer a minimal child environment so an approved runtime does not receive unrelated provider credentials.
- For Codex and Claude, consume a structured machine-readable assistant result or an exact isolated response field. Never verify by searching combined prompt, stdout, and stderr.
- Parse OpenAI and OpenRouter JSON and require an exact assistant response after bounded normalization. Never substring-match the entire raw response body.
- Require explicit imperative delegation such as `use the recommended one`; questions or requests for information about the best/default option must remain unresolved.
- Add adversarial regression tests for secret-bearing stderr, argv-echo false positives, refusal-text HTTP responses, and selection questions.
- Rerun package-local, packed-artifact, PTY, and available CI checks from the exact repaired head.

## Ledger reconciliation

The campaign staging record and this spec are returned to `todo`. `WF-CLI-002` remains dependency-gated. The canonical `main` backlog currently has no WF-CLI rows, so no unrelated large-ledger replacement was attempted; the staging record remains the review queue under the documented fallback rule.

No live provider call was made. No package was published. No installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
