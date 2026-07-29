# Tasks: Origin Minimal Bootstrap

**Input**: `spec.md`, `plan.md`, `.specify/memory/constitution.md`

**Canonical status**: The branch Rail at `docs/campaigns/cli-socratic-bootstrap/operations/ledger.json` owns live status, dependencies, evidence, and completion. This file owns decomposition and traceability only.

## Phase 1: Constitutional and Scope Gate

- [x] **T001 [US1]** Verify the proposal against recovered Constitutional Architectonics doctrine and current Architectonic contracts in `docs/campaigns/cli-socratic-bootstrap/CONSTITUTIONAL-ALIGNMENT.md`.
- [x] **T002 [US1]** Run the Ponytail delete/reuse pass and define the MVP in `docs/campaigns/cli-socratic-bootstrap/LEAN-SCOPE.md`.
- [x] **T003 [US1]** Create an empty branch-specific Rail before adding implementation tickets.

## Phase 2: Spec Kit Contract

- [x] **T004 [US1]** Add the branch constitution at `.specify/memory/constitution.md`.
- [x] **T005 [US1]** Add feature specification and implementation plan under `specs/001-origin-minimal-bootstrap/`.
- [x] **T006 [US1]** Translate these tasks into branch Rail items with dependencies and acceptance criteria.

## Phase 3: User Story 1 — Safe Formation Plan (MVP)

- [x] **T007 [US3]** Add `packages/workframe/bin/workframe-cli.js` to dispatch `start` and delegate all other commands to the existing `workframe.js`.
- [x] **T008 [US1]** Add `packages/workframe/bin/origin-start.js` with purpose capture, bounded provisional-form parsing, current status invocation, candidate selection, and zero-mutation plan output.
- [x] **T009 [US1]** Update `packages/workframe/package.json` so the package binary uses the thin dispatcher and the package test runs Origin checks.

**Checkpoint**:

```bash
workframe start --json \
  --purpose="Build a durable operating context for my work." \
  --forms=business,project
```

returns a valid zero-mutation plan while existing commands remain delegated.

## Phase 4: User Story 2 — Purpose Before Structure

- [x] **T010 [US2]** Add TTY prompting that asks for purpose and success before asking whether organization, business, project, or none yet should carry it.
- [x] **T011 [US2]** Add human-readable output that states no files were inspected and nothing changed.

## Phase 5: Verification and Documentation

- [x] **T012 [US1]** Add `packages/workframe/scripts/test-origin-start.mjs` using Node `assert` and child-process execution.
- [ ] **T013 [US3]** Verify the exact packed package on a real checkout and supported host, including `node --check`, package tests, existing delegated status output, and Origin JSON output.
- [x] **T014 [US1]** Update `packages/workframe/README.md` with the experimental plan-only command and privacy boundary.
- [x] **T015 [US1]** Run a Ponytail review on the implementation diff and remove anything not required by the acceptance scenarios.

## Deferred Features — Not Tickets in This Rail

- progressive path authorization and metadata inventory;
- source-content inspection;
- LLM-guided Socratic question ranking;
- Architectonic instantiation;
- source mount/copy/clone planning;
- project Rail creation;
- Workframe installation and runtime attachment;
- hosted inference fallback.

Each deferred feature requires a separate Spec Kit feature and may be rejected entirely if an existing Architectonic or Workframe surface covers it.
