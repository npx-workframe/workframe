# Feature Specification: Origin Minimal Bootstrap

**Feature Branch**: `feat/origin-minimal-bootstrap`

**Created**: 2026-07-29

**Status**: In progress

**Input**: Add the smallest teleology-first formation entrypoint to the existing Workframe CLI without changing current runtime discovery or building the later scanning, ontology, installation, and workspace system.

## User Scenarios & Testing

### User Story 1 - Get a Safe Formation Plan (Priority: P1)

A user runs:

```bash
workframe start --json \
  --purpose="Build a durable operating context for my work." \
  --forms=business,project
```

The command returns a deterministic plan that records the user's purpose statement before the provisional organizational forms, identifies the best already-detected inference candidate, states that authorization is still required, and confirms that no paths were inspected and no mutations occurred.

**Why this priority**: It proves the product thesis and constitutional order without requiring an LLM, filesystem access, or installation.

**Independent Test**: Run the command in a fixture environment and verify valid JSON, purpose, provisional forms, candidate priority, empty `inspected_paths`, and empty `mutations`.

**Acceptance Scenarios**:

1. **Given** Codex is authenticated, **When** the user provides a purpose and provisional forms, **Then** Codex is named as a candidate but not authorized or invoked.
2. **Given** no runtime or provider is available, **When** the user provides a purpose, **Then** the plan remains valid with a null candidate and no mutation.
3. **Given** the command runs non-interactively without a purpose, **When** JSON is requested, **Then** it returns a plan with a null purpose and asks the teleological first question.
4. **Given** a purpose but no form, **When** the plan is produced, **Then** the next question asks what durable form, if any, should carry that purpose.

---

### User Story 2 - Answer Purpose Before Structure (Priority: P2)

A terminal user runs `workframe start`, describes what they are trying to accomplish, for whom, and what success looks like, then optionally chooses organization, business, project, or none yet.

**Why this priority**: It makes the first slice useful to nontechnical users while preserving the paper's teleology-before-ontology order.

**Independent Test**: Provide representative form strings to the parser and verify normalization, deduplication, and `none yet` handling. Verify that purpose remains a plain user statement and is not interpreted as established doctrine.

**Acceptance Scenarios**:

1. **Given** a TTY, **When** the user states a purpose and answers `1, project`, **Then** the result contains the purpose plus `organization` and `project` once each.
2. **Given** the user selects `none, project`, **When** forms are normalized, **Then** `project` wins and `none` is removed.
3. **Given** the user provides no purpose, **When** the flow ends, **Then** no form is invented and the next question remains the purpose question.

---

### User Story 3 - Preserve Existing CLI Behavior (Priority: P1)

A current user continues to run `workframe`, `workframe status`, `workframe help`, and `workframe version` without behavior being reimplemented or routed through new formation logic.

**Why this priority**: The new capability must not destabilize the already-shipped detector.

**Independent Test**: Invoke the wrapper with a non-`start` command and verify delegation to the existing CLI entrypoint.

**Acceptance Scenarios**:

1. **Given** any existing command, **When** invoked through the package binary, **Then** the existing `workframe.js` implementation handles it.
2. **Given** `start`, **When** invoked through the same binary, **Then** only the bounded Origin module handles it.

### Edge Cases

- Duplicate form aliases must collapse to one canonical value.
- `none yet` must remain valid when selected alone and disappear when a concrete form is also selected.
- Provider environment presence must never expose the value.
- An invalid or malformed status response must fail with a clear error and no mutation.
- JSON mode must not prompt.
- A detected but unauthenticated runtime must not outrank an authenticated runtime or configured provider.
- Windows command behavior for existing commands remains owned by the existing CLI.

## Requirements

### Functional Requirements

- **FR-001**: The package binary MUST recognize `start` as a new command.
- **FR-002**: Every command other than `start` MUST delegate to the existing CLI entrypoint unchanged.
- **FR-003**: `start` MUST obtain environment status by invoking the existing `status --json` command path.
- **FR-004**: `start` MUST support `--json`, `--purpose=<text>`, and `--forms=<comma-separated-values>`.
- **FR-005**: Interactive mode MUST ask for purpose before asking for form.
- **FR-006**: Form parsing MUST recognize organization, business, project, and none plus bounded numeric and short aliases.
- **FR-007**: Candidate selection MUST prefer authenticated Codex, verified Claude, verified Hermes, then configured providers.
- **FR-008**: Output MUST state that authorization remains required.
- **FR-009**: Output MUST contain empty `inspected_paths` and `mutations` arrays in this feature.
- **FR-010**: The feature MUST make no provider call and perform no filesystem mutation.
- **FR-011**: The feature MUST add no runtime dependency.
- **FR-012**: A runnable check MUST verify form parsing, candidate selection, constitutional order, zero-mutation output, and command execution.
- **FR-013**: Help and package documentation MUST identify `start` as experimental and plan-only.

### Key Entities

- **Purpose Statement**: User-supplied language describing desired outcome, beneficiary, and success. It is not yet accepted doctrine.
- **Candidate Form**: Organization, business, project, or none yet. It is provisional ontology, not purpose.
- **Inference Candidate**: A detected runtime or configured provider that may later be authorized; it is not a grant.
- **Formation Plan**: A zero-mutation JSON or human-readable result containing purpose, candidate forms, inference candidate, authorization posture, inspected paths, mutations, and next question.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Existing status, help, and version routes remain delegated to the original implementation.
- **SC-002**: All included checks pass using Node.js 20 or later.
- **SC-003**: The JSON plan contains no path, credential value, provider call result, or mutation.
- **SC-004**: The first question concerns purpose and success, not entity type or installation.
- **SC-005**: A user can reach a valid plan with one command and two bounded inputs.
- **SC-006**: The implementation adds no external dependency and no duplicate runtime scanner.

## Assumptions

- The current `workframe.js status --json` output remains the discovery contract for this slice.
- A purpose statement remains provisional until later evidence review and explicit acceptance.
- Later features will add progressive path grants rather than broad scanning.
- Architectonic will own durable composition and validation when formation advances beyond planning.
- Workframe/create-workframe will own workspace installation and runtime operation.
