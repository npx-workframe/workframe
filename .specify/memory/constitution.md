# Workframe Origin Minimal Bootstrap Constitution

## Core Principles

### I. Purpose Before Structure

Every formation flow MUST begin by establishing what the user is trying to accomplish before proposing ontology, files, agents, tools, or installation. A detected environment does not define the user's purpose.

### II. Reuse Existing Authorities

Runtime discovery MUST reuse the existing Workframe status command. Durable organization structure MUST be delegated to Architectonic. Workspace installation and runtime operation MUST be delegated to Workframe/create-workframe. This feature MUST NOT create parallel discovery, ontology, credential, workspace, or work-ledger systems.

### III. Progressive Consent

Discovery, content inspection, external transmission, credential use, and mutation are separate grants. Access MUST NOT be inferred from detection. The first feature slice MUST inspect no user paths, call no provider, and write no user state.

### IV. Files and Evidence Over Chat

Chat and model inference are temporary coordination surfaces. Durable claims require recoverable evidence or explicit user confirmation. Facts, decisions, assumptions, contradictions, and known unknowns MUST remain distinguishable.

### V. Minimum Coherent Slice

Follow the Ponytail ladder: avoid building, reuse local code, use platform capabilities, add no dependency, and implement only the minimum independently testable slice. Security, accessibility, trust-boundary validation, and data-loss prevention are not simplification targets.

## Technical Constraints

- Node.js 20 or later.
- No new runtime dependency for the initial feature.
- Existing `status`, `help`, and `version` behavior must remain available through the same `workframe` executable.
- `start` is plan-only in the initial feature.
- JSON output must be stable enough for tests and future composition.
- No secrets, private paths, or credential values may appear in output.

## Development Workflow

1. Read the current CLI flow before changing dispatch.
2. Keep the old status implementation intact.
3. Add one thin dispatch and one bounded formation module.
4. Leave one runnable test that verifies parsing, candidate selection, zero mutations, and command output.
5. Track live work only in the branch Rail at `docs/campaigns/cli-socratic-bootstrap/operations/ledger.json`.
6. Spec Kit `tasks.md` describes the feature decomposition; the Rail is the canonical current status and evidence authority.

## Governance

This constitution governs only `feat/origin-minimal-bootstrap`. Amendments require a documented reason, a smaller alternative considered, and an update to the branch Rail. The constitutional Architectonics paper and canonical Architectonic contracts outrank this local development constitution when they conflict.

**Version**: 0.1.0 | **Ratified**: 2026-07-29 | **Last Amended**: 2026-07-29
