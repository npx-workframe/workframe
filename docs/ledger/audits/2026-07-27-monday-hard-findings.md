# Monday morning hard findings — 2026-07-27

**Verified:** 2026-07-21  
**Source:** `main` at `6108bc0f3e4e1b28afa1a658cd92d18eb1298527`  
**Scope:** standalone `packages/workframe` CLI only

Only source-demonstrable findings are recorded here. Do not expand this note into speculative redesign.

## WF-AUD-001 — ambiguous language can authorize a paid provider call

**Severity:** P1 — authority boundary

`interpretConsent()` treats the standalone word `please` as affirmative consent. `askForTest()` performs the provider call whenever that parser returns `yes`.

Source:

- `packages/workframe/bin/workframe.js`
- `yesPatterns` contains `/\bplease\b/`
- the first or second parsed answer is accepted without requiring an affirmative action clause

Deterministic reproduction:

```text
please explain what this does first
```

This contains no authorization to run the test, but the current parser returns `yes` and proceeds to `runTest()`.

### Required correction

- Remove politeness-only tokens such as `please` from affirmative consent.
- Require an explicit affirmative action phrase tied to the proposed test.
- Keep negative language dominant.
- Add replay tests for questions, hedging, explanation requests, conditional language, and mixed positive/negative phrases.

### Interim operator instruction

Until corrected, use `workframe status --no-test` or `workframe status --json` when no provider call is intended.

## WF-AUD-002 — link verification accepts marker text outside structured assistant output

**Severity:** P1 — false verification

The current adapters declare success when `WORKFRAME_OK` appears anywhere in:

- raw Codex stdout plus stderr;
- raw Claude stdout plus stderr;
- the entire OpenAI HTTP response body;
- the entire OpenRouter HTTP response body.

The validator does not parse a structured assistant-response field and does not require exact equality. A prompt echo, diagnostic line, refusal explanation, wrapper output, or unrelated JSON field containing the marker can therefore produce `LINK VERIFIED` without proving a valid assistant response.

Source:

- `packages/workframe/bin/workframe.js`
- `runTest()` uses `/WORKFRAME_OK/i.test(...)`
- `testOpenAI()` and `testOpenRouter()` test the raw response body

### Required correction

- Parse the provider-specific structured assistant output.
- Normalize it and require exact equality with `WORKFRAME_OK`.
- Never inspect stderr, prompt echoes, request payloads, or diagnostic text as success evidence.
- Add negative fixtures where the marker appears only in the prompt, stderr, refusal text, or metadata.

## WF-AUD-003 — package documentation reports the previous version

**Severity:** P3 — release truth

`packages/workframe/package.json` is version `0.2.1`, while `packages/workframe/README.md` describes “Version `0.2.0`” as the current read-only release.

### Required correction

Update the README wording or make it version-neutral before the next package publication.

## Monday stop line

Do not add model-assisted Socratic behavior or composition/deployment work before WF-AUD-001 and WF-AUD-002 are closed with packed-package tests. These findings are confined to the standalone CLI and do not alter the separate `create-workframe` product ledger.