# Implementation Plan: Origin Minimal Bootstrap

**Branch**: `feat/origin-minimal-bootstrap` | **Date**: 2026-07-29 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `specs/001-origin-minimal-bootstrap/spec.md`

## Summary

Add a thin package entrypoint that routes only `start` to a small formation module and delegates every existing command to the shipped CLI unchanged. The formation module invokes existing `status --json`, captures a purpose statement first, parses an optional bounded form second, identifies an inference candidate, and emits a zero-mutation plan. No scanning, LLM call, credential import, Architectonic installation, or Workframe deployment is included.

## Technical Context

**Language/Version**: Node.js 20+

**Primary Dependencies**: Node.js standard library only

**Storage**: None

**Testing**: Node `assert` and child-process checks

**Target Platform**: Windows, macOS, Linux CLI

**Project Type**: Existing npm CLI package

**Performance Goals**: Finish after the existing status probes; no additional network latency

**Constraints**: No new dependency, no write path, no provider call, preserve existing command behavior

**Scale/Scope**: One command, one purpose string, one bounded form parser, one plan object, one runnable check

## Constitution Check

- Purpose before structure: pass; `start` captures purpose before provisional form.
- Reuse existing authorities: pass; status is invoked, not reimplemented.
- Progressive consent: pass; no path or provider access occurs.
- Files/evidence over chat: pass; the purpose remains a provisional user statement and no durable claim is written.
- Minimum coherent slice: pass; two small runtime files and one test.

## Project Structure

### Documentation

```text
.specify/
├── feature.json
└── memory/constitution.md

specs/001-origin-minimal-bootstrap/
├── spec.md
├── plan.md
└── tasks.md

docs/campaigns/cli-socratic-bootstrap/
├── CONSTITUTIONAL-ALIGNMENT.md
├── LEAN-SCOPE.md
└── operations/ledger.json
```

### Source Code

```text
packages/workframe/
├── bin/
│   ├── workframe.js          # existing implementation, unchanged
│   ├── workframe-cli.js      # thin command dispatch
│   └── origin-start.js       # bounded plan-only formation flow
├── scripts/
│   └── test-origin-start.mjs
├── package.json
└── README.md
```

**Structure Decision**: Keep the existing CLI intact. Add one dispatcher because the existing file self-executes and exports no reusable command boundary. Keep formation logic in one separate file so it can be tested without modifying the established status implementation.

## Complexity Tracking

No constitutional exceptions. A wrapper is justified because editing or duplicating the current 400-line CLI would be a larger and riskier change than delegating it intact.
