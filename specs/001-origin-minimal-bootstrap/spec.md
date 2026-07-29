# Feature Specification: Origin Minimal Bootstrap

**Feature Branch**: `feat/origin-minimal-bootstrap`

**Created**: 2026-07-29

**Status**: In progress

**Input**: Add the smallest teleology-first formation entrypoint to the existing Workframe CLI without changing current runtime discovery or building the later scanning, ontology, installation, and workspace system.

## User Scenarios & Testing

### User Story 1 - Get a Safe Formation Plan (Priority: P1)

A user runs `workframe start --json --goals=business,project` and receives a deterministic plan that records the selected goals, identifies the best already-detected inference candidate, states that authorization is still required, and confirms that no paths were inspected and no mutations occurred.

**Why this priority**: It proves the product thesis and command boundary without requiring an LLM, filesystem access, or installation.

**Independent Test**: Run the command in a fixture environment and verify valid JSON, selected goals, candidate priority, empty `inspected_paths`, and empty `mutations`.

**Acceptance Scenarios**:

1. **Given** Codex is authenticated, **When** the user requests a business and project plan, **Then** Codex is named as a candidate but not authorized or invoked.
2. **Given** no runtime or provider is available, **When** the user requests a project plan, **Then** the plan remains valid with a null candidate and no mutation.
3. **Given** the command runs non-interactively without goals, **When** JSON is requested, **Then** it returns a plan with no selected goals and asks the teleological first question.

---

### User Story 2 - Answer the First Question Conversationally (Priority: P2)

A terminal user runs `workframe start`, chooses one or more of organization, business, and project using numbers or plain words, and receives a human-readable summary and next question.

**Why this priority**: It makes the first slice useful to nontechnical users while preserving deterministic interpretation for the bounded initial choice.

**Independent Test**: Provide representative goal strings to the parser and verify normalization, deduplication, and rejection of unsupported values.

**Acceptance Scenarios**:

1. **Given** a TTY, **When** the user answers `1, project`, **Then** the result contains `organization` and `project` once each.
2. **Given** an invalid answer, **When** no recognized goal is found, **Then** no goal is invented and the next question remains the goal question.

---

### User Story 3 - Preserve Existing CLI Behavior (Priority: P1)

A current user continues to run `workframe`, `workframe status`, `workframe help`, and `workframe version` without behavior being reimplemented or routed through new formation logic.

**Why this priority**: The new capability must not destabilize the already-shipped detector.

**Independent Test**: Invoke the wrapper with a non-`start` command and verify delegation to the existing CLI entrypoint.

**Acceptance Scenarios**:

1. **Given** any existing command, **When** invoked through the package binary, **Then** the existing `workframe.js` implementation handles it.
2. **Given** `start`, **When** invoked through the same binary, **Then** only the bounded Origin module handles it.

### Edge Cases

- Duplicate goal aliases must collapse to one canonical value.
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
- **FR-004**: `start` MUST support `--json` and `--goals=<comma-separated-values>`.
- **FR-005**: Goal parsing MUST recognize organization, business, and project plus bounded numeric and short aliases.
- **FR-006**: Candidate selection MUST prefer authenticated Codex, verified Claude, verified Hermes, then configured providers.
- **FR-007**: Output MUST state that authorization remains required.
- **FR-008**: Output MUST contain empty `inspected_paths` and `mutations` arrays in this feature.
- **FR-009**: The feature MUST make no provider call and perform no filesystem mutation.
- **FR-010**: The feature MUST add no runtime dependency.
- **FR-011**: A runnable check MUST verify parsing, candidate selection, zero-mutation output, and command execution.
- **FR-012**: Help and package documentation MUST identify `start` as experimental and plan-only.

### Key Entities

- **Formation Goal**: One of organization, business, or project selected explicitly by the user.
- **Inference Candidate**: A detected runtime or configured provider that may later be authorized; it is not a grant.
- **Formation Plan**: A zero-mutation JSON or human-readable result containing goals, candidate, authorization posture, inspected paths, mutations, and next question.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Existing status, help, and version routes remain delegated to the original implementation.
- **SC-002**: All included checks pass using Node.js 20 or later.
- **SC-003**: The JSON plan contains no path, credential value, provider call result, or mutation.
- **SC-004**: A user can reach a valid plan with one command and one bounded answer.
- **SC-005**: The implementation adds no external dependency and no duplicate runtime scanner.

## Assumptions

- The current `workframe.js status --json` output remains the discovery contract for this slice.
- Later features will add progressive path grants rather than broad scanning.
- Architectonic will own durable composition and validation when formation advances beyond planning.
- Workframe/create-workframe will own workspace installation and runtime operation.
