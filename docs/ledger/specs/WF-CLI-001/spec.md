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

- the branch is rebuilt from current `main`, is zero commits behind, and is mergeable;
- cancellation is threaded through the terminal, HTTP request, and asynchronous child-process interfaces;
- account-backed and direct API-key candidates are separate;
- inference child environments exclude Docker, SSH, unrelated credentials, and arbitrary ambient variables;
- structured provider parsers require the exact `WORKFRAME_OK` assistant response.

Blocking findings:

1. **Candidate mentions still authorize a path without affirmative selection.** The parser selects a candidate whenever one unhedged term appears, regardless of whether the sentence is descriptive or distrustful. Exact reproductions against the reviewed parser:

   ```text
   "I don't know anything about Claude." → claude-account
   "I don't trust OpenRouter." → openrouter-api
   "Claude is installed." → claude-account
   "Claude sounds risky." → claude-account
   ```

   These are not selections. They violate the requirement that descriptive, negative-context, and non-imperative language remain unresolved.

2. **Exclusions can select an unrelated provider.** `isExcluded` applies the first exclusion marker to every later candidate term within a global 48-character window. Exact reproductions:

   ```text
   "Don't use Claude; use Codex." → openrouter-api
   "Not Claude, use Codex." → openrouter-api
   ```

   Both named paths are incorrectly excluded, and the sole unmentioned remaining candidate is silently chosen.

3. **Windows cancellation is not proven fail-closed.** The production Windows terminator starts `taskkill` detached and unrefed but does not observe its spawn error, exit code, or completion. `runChildCommand` then settles as cancelled after 750 ms even if the runtime child tree remains alive. The current test injects a custom terminator that kills the fake child directly, so it bypasses the production `taskkill` path.

4. **The explicit exact-head CI gate is red.** CI run `29356707079` failed at `Harness verify`; downstream package-install and negative-install steps were skipped. The repository workflow also does not independently execute the package-local and packed-tarball matrix recorded by the implementer.

## Required remediation

- Require affirmative selection syntax for named candidates, or parse positive and negative clauses explicitly so mere mentions cannot select a path.
- Scope each exclusion to the candidate clause it modifies; never choose an unrelated remaining candidate from ambiguous multi-clause text.
- Add regression tests for every exact phrase listed in this review.
- On Windows, await and verify `taskkill` completion, handle spawn and nonzero-exit failures, and do not return a cancelled result while the runtime process may still be alive.
- Add a Windows test that exercises the production `.cmd` plus `taskkill` path instead of an injected direct kill.
- Add package-local and packed-tarball checks to exact-head CI and obtain a green or explicitly isolated repository result before resubmission.

## Evidence boundary

The implementer reported 18/18 package tests, a clean packed install, valid status JSON, and a real-PTY Ctrl+C cancellation result on Linux. This review retained those as implementer evidence but did not treat them as independent acceptance because the exact-head CI gate is red and Windows production termination remains untested.

`WF-CLI-002` remains dependency-gated. `now.md` is unchanged because this slice has not been accepted or shipped. No live provider was called, no package was published, and no installation, runtime, service, app, infrastructure path, or non-CLI code was modified.
