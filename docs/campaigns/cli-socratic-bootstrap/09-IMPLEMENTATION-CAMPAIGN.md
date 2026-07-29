# Isolated Implementation Campaign

## 1. Campaign mandate

Build Workframe Origin as a separate CLI construction campaign that learns from Workframe, Architectonic, Rail, Agents, Knowledge, and ABKB without altering their canonical meaning during the campaign's initial development.

The campaign begins with contracts, fixtures, and a runnable prototype. Integration with the existing `workframe` package, `create-workframe`, Workframe API/UI, or Architectonic packages occurs only after explicit review and acceptance.

## 2. Isolation rules

### Required

- Work on a dedicated branch or worktree.
- Keep the campaign's doctrine and design under `docs/campaigns/cli-socratic-bootstrap/`.
- Prototype implementation behind a new, clearly isolated package or experimental path.
- Reuse current source through documented interfaces, not direct edits to donor repositories.
- Treat ABKB as an instantiation reference, not as distributable product content.
- Use fixtures instead of scanning developer machines in tests.
- Keep all external inference disabled in automated tests unless a dedicated integration flag and test credential are present.
- Preserve current `workframe status` behavior until a replacement passes compatibility tests.

### Prohibited

- No modification of Architectonic sibling repositories as part of this campaign without a separate request.
- No copying private ABKB identity or project content into public fixtures.
- No assumption that existing Workframe install paths, APIs, or runtime profiles are stable public contracts.
- No whole-disk scan prototype.
- No model-generated shell execution.
- No silent use of local credentials.
- No direct merge into `main` before campaign exit gates pass.
- No attempt to solve current Workframe product backlog while working this campaign.

## 3. Recommended prototype boundary

The first implementation should remain structurally isolated while using the future package name only at the CLI shim.

```text
packages/
├─ workframe/                       # current package; compatibility surface
└─ workframe-origin/                # campaign implementation until accepted
   ├─ bin/
   │  └─ workframe-origin.js
   ├─ src/
   │  ├─ cli/
   │  ├─ discovery/
   │  ├─ consent/
   │  ├─ adapters/
   │  ├─ scanner/
   │  ├─ evidence/
   │  ├─ formation/
   │  ├─ architectonic/
   │  ├─ attachments/
   │  ├─ agents/
   │  ├─ workframe/
   │  ├─ transactions/
   │  └─ verification/
   ├─ protocol/
   ├─ schemas/
   ├─ prompts/
   ├─ fixtures/
   └─ test/
```

Alternative names such as `packages/workframe-cli-next/` are acceptable. The invariant is an isolated dependency graph and executable. Once accepted, the canonical `workframe` bin may delegate to the new implementation.

## 4. Workstreams

### WS-01 — Product and protocol contracts

Deliver:

- formation-stage contract;
- grant schema;
- evidence schema;
- attachment schema;
- runtime-adapter contract;
- transaction-plan schema;
- installed-agent binding schema;
- Workframe attachment contract;
- completion and verification contract;
- controlled vocabulary and error model.

Exit gate:

- schemas validate representative fixtures;
- no source code depends on unstated prompt behavior;
- terminology aligns with this campaign and does not redefine canonical Architectonic layers.

### WS-02 — Runtime discovery extraction

Refactor or reproduce the current read-only CLI detector behind adapter contracts.

Initial adapters:

- Hermes;
- Codex CLI;
- Claude Code;
- Pi;
- OpenClaw;
- Cursor Agent;
- OpenRouter environment;
- OpenAI environment;
- Anthropic environment;
- Gemini/Google environment.

Deliver:

- safe Windows, macOS, and Linux executable resolution;
- version probes;
- documented auth-status probes;
- normalized statuses;
- redacted JSON and human output;
- timeouts and cancellation;
- no mutation assertion tests.

Exit gate:

- current `workframe status --json` fixture behavior remains representable;
- no probe reads private auth stores;
- no provider call occurs without an explicit integration-test grant.

### WS-03 — Consent authority

Deliver:

- structured grants;
- natural-language answer interpretation compiled to grants;
- grant review screen;
- nested scopes;
- expiry and revocation;
- audit receipts;
- refusal and ambiguity behavior;
- noninteractive flag behavior.

Exit gate:

- ambiguous answers cannot create sensitive grants;
- external inference and filesystem content access are separate capabilities;
- all mutating commands require a plan and grant.

### WS-04 — Secure inference router

Deliver:

- use-in-place CLI invocation;
- environment-key use-in-place;
- secure new-key input;
- Workframe vault integration adapter stub;
- hosted relay interface stub;
- bounded request envelope;
- source/evidence ID receipts;
- cancellation and budget controls.

Exit gate:

- test adapters can prove that only approved excerpts are transmitted;
- raw credential values never enter logs or state files;
- silent provider fallback is impossible.

### WS-05 — Progressive scanner

Deliver:

- root selection;
- metadata inventory;
- repository detection;
- file inventory;
- content extraction adapters for Markdown, text, common code, JSON, YAML, and selected document formats;
- ignore rules;
- path escape defense;
- size/count/time budgets;
- sensitive-path stop heuristics;
- local-only mode;
- fixture filesystem.

Exit gate:

- scanner cannot escape fixture roots through symlinks or junctions;
- archives and hidden files are excluded by default;
- a content grant does not imply external inference;
- inventories can be deleted independently of canonical outputs.

### WS-06 — Evidence and contradiction engine

Deliver:

- evidence item registry;
- source authority and staleness fields;
- fact/decision/assumption/inference/unknown/contradiction classifications;
- model proposal parser;
- deterministic validation;
- contradiction grouping;
- question candidate ranking;
- provenance rendering.

Exit gate:

- generated claims are visibly marked as proposals;
- contradictions remain preserved until accepted resolution;
- each accepted fact or decision can route to recoverable evidence or explicit user answer.

### WS-07 — Formation state machine

Deliver:

- resumable stages;
- stage prerequisites;
- adaptive question selection;
- question-history deduplication;
- skip and pause;
- one-question-at-a-time mode;
- detailed/expert mode;
- checkpointing;
- completion threshold based on operational grounding, not filled fields;
- deterministic-only fallback script.

Exit gate:

- interrupted sessions resume without repeating resolved questions;
- the system can complete a project-only path without manufacturing an organization;
- the system can recommend no installation for disposable work;
- the system preserves open questions.

### WS-08 — Architectonic planner and compiler

Deliver:

- durable-concern to layer/profile planner;
- smallest-closure recommendation;
- `no installation` outcome;
- upstream package source and version recording;
- local document map;
- template instantiation from accepted evidence and decisions;
- canonical file write targets;
- provenance blocks;
- dry-run diffs;
- verification invocation.

Exit gate:

- no local facts are invented to complete templates;
- upstream package files and local user-owned files remain distinct;
- existing Architectonic installations route to inspect/reopen/adopt/extend instead of overwrite;
- generated files pass Architectonic verification for supported profiles.

### WS-09 — Source attachment and repository organizer

Deliver:

- reference;
- adopt existing repository;
- clone repository;
- read-only attachment;
- read-write attachment;
- copy snapshot;
- import extract;
- attachment provenance;
- detach and revoke;
- project-to-repository many-to-many mapping.

Exit gate:

- existing repositories are never moved silently;
- read-only and read-write modes are enforced distinctly;
- copies record source, time, and hash;
- every project can list its canonical and supporting repositories.

### WS-10 — Project and Rail formation

Deliver:

- project contract generation;
- standalone project support;
- organization project registry;
- Rail justification gate;
- one ledger root per Rail-enabled project;
- initial bounded work items;
- role eligibility;
- evidence and review gates;
- Rail validation and ready-item selection tests.

Exit gate:

- no project has parallel canonical queues;
- no Rail is created for fixture scenarios that do not require durable coordination;
- agents can select only eligible ready items.

### WS-11 — Agent and permission binder

Deliver:

- archetype selection;
- installed-agent files;
- human owner;
- organization/project scope;
- runtime adapter binding;
- model and funding policy;
- source/attachment access;
- skills and knowledge attachments;
- spending and external-action boundaries;
- approval/review/escalation/stop rules;
- startup-context generation.

Exit gate:

- no agent verifies without owner and stop authority;
- delegation cannot exceed delegator grants;
- agent runtime profiles cannot read unrelated project attachments in tests;
- runtime instructions route to canonical Architectonic files rather than duplicating doctrine.

### WS-12 — Workframe attachment

Deliver:

- repository-only outcome;
- local single-user adapter;
- existing Workframe attachment adapter;
- user/role mapping;
- project/Space mapping;
- agent route/profile mapping;
- files and attachment mapping;
- vault/use-in-place credential mapping;
- Rail views;
- workspace startup and health verification.

Exit gate:

- a fresh session loads accepted purpose, authority, project, sources, and Rail;
- raw secrets are not mounted into shared runtime paths;
- Workframe views do not become competing canonical sources;
- repository-only mode remains fully supported.

### WS-13 — Accessibility and trust UX

Deliver:

- simple, guided, and detailed modes;
- large-print and high-contrast output;
- screen-reader-friendly flow;
- explicit back/repeat/explain/skip/pause/stop controls;
- native file selection where available;
- no default-sensitive consent;
- plain-language data-flow summaries;
- expert exact plan and receipt views.

Exit gate:

- keyboard-only completion;
- 200% zoom/native wrapper fixture passes when a GUI exists;
- users can correctly identify what was scanned and what was transmitted;
- confusion does not produce consent.

### WS-14 — Security and adversarial verification

Deliver:

- path traversal tests;
- symlink/junction escape tests;
- prompt-injection corpus;
- secret redaction tests;
- grant-bypass tests;
- malicious adapter output tests;
- partial transaction recovery;
- provider fallback denial;
- permission escalation denial;
- private-zone exclusion proof;
- audit receipt review.

Exit gate:

- all security acceptance criteria in `08-SECURITY-PRIVACY-AUTHORITY.md` pass;
- an independent reviewer signs off on the threat model and evidence.

## 5. Phases

### Phase 0 — Campaign freeze and contracts

Goal: establish stable vocabulary, schemas, fixtures, and non-goals before implementation.

Outputs:

- approved campaign docs;
- JSON schemas;
- fixture personas and filesystems;
- adapter interface;
- state machine;
- security model;
- initial acceptance matrix.

No production integration.

### Phase 1 — Read-only local link

Goal: turn the existing runtime detector into a tested adapter registry and consent-aware status surface.

Demonstration:

```bash
workframe-origin status --json
workframe-origin start --fixture novice-windows
```

No content scan or Architectonic write.

### Phase 2 — Authorized evidence inventory

Goal: select roots, inventory metadata, classify project candidates, exclude private zones, and produce a redacted local report.

No external inference required.

### Phase 3 — Socratic formation core

Goal: complete teleology, ontology, epistemology, doctrine, identity, constitution, and one project using fixtures and one approved model adapter.

Output: resumable formation state plus proposed files; no Workframe deployment.

### Phase 4 — Architectonic materialization

Goal: compile accepted formation into a valid Architectonic instance, adopt or clone one repository, and create one justified Rail.

Output: repository-only usable result.

### Phase 5 — Agent and runtime continuity

Goal: bind one project agent and one specialist to two runtime adapters; demonstrate a new session entering from canonical files and Rail.

### Phase 6 — Workframe local attachment

Goal: deploy or attach a local single-user Workframe and display the same projects, files, agents, permissions, and Rail.

### Phase 7 — Accessibility and real-machine dogfood

Goal: supervised tests across Windows, macOS, and Linux with novice, skeptical, expert, and highly customized-machine scenarios.

### Phase 8 — Integration decision

Choose one:

```text
merge as canonical workframe CLI
ship as an experimental command/package
retain as separate Workframe Origin product mode
revise campaign
archive campaign
```

This decision must be evidence-based and explicit.

## 6. Fixture program

### Fixture A — Grandmother Windows

- Windows paths;
- high-zoom/simple mode;
- no existing runtime;
- small Workframe-funded allowance or deterministic-only;
- one personal project;
- no Git requirement;
- no organization or Rail unless justified.

### Fixture B — Skeptical psychiatrist Mac

- Claude Code authenticated;
- private clinical exclusion tree;
- public website repo;
- seminar documents;
- multiple scopes;
- local-only sources;
- strict publication and privacy constitution.

### Fixture C — Capable but non-current builder

- several runtimes;
- API keys in environment;
- mixed repositories and notes;
- project-system recommendation;
- guided mode.

### Fixture D — Old-school programmer Windows/Linux

- customized paths;
- existing checkouts;
- explicit no-move rule;
- detailed commands and dry run;
- local-only use-in-place runtime;
- repository-only outcome accepted.

### Fixture E — Agentic power user

- existing Architectonic and Workframe markers;
- several organizations/projects;
- multiple runtimes and providers;
- agents and Rails already present;
- inspect/adopt/reconcile path rather than scaffold.

### Fixture F — Disposable task

- one-session purpose;
- correct recommendation: no installation.

## 7. Campaign Rail

If implementation begins, create one campaign Rail under the isolated branch or campaign workspace. Do not add competing task files.

Suggested epics:

```text
ORIGIN-001 protocol and schemas
ORIGIN-002 runtime adapters
ORIGIN-003 consent authority
ORIGIN-004 scanner
ORIGIN-005 evidence and contradiction engine
ORIGIN-006 formation state machine
ORIGIN-007 Architectonic compiler
ORIGIN-008 attachments and repositories
ORIGIN-009 projects and Rail
ORIGIN-010 agents and permissions
ORIGIN-011 Workframe attachment
ORIGIN-012 accessibility
ORIGIN-013 security verification
ORIGIN-014 dogfood and integration decision
```

Each item requires:

- bounded deliverable;
- source basis;
- dependencies;
- eligible role;
- required evidence;
- review gate;
- completion criteria;
- one ledger transition.

## 8. Verification strategy

### Unit

- path normalization;
- grant matching;
- schema validation;
- adapter parsing;
- question deduplication;
- layer closure;
- Rail uniqueness;
- redaction.

### Fixture integration

- full deterministic-only path;
- full use-in-place Claude path;
- local-only source path;
- external excerpt approval path;
- pause/resume;
- revoke/detach;
- existing install adoption;
- partial apply recovery.

### End to end

```text
fresh machine fixture
  -> status
  -> inference consent
  -> evidence inventory
  -> Socratic formation
  -> Architectonic plan
  -> apply
  -> attach repository
  -> create Rail
  -> bind agents
  -> attach Workframe
  -> start fresh runtime session
  -> verify correct context and permissions
```

### Adversarial

- malicious local README prompt injection;
- source containing fake permission grant;
- symlink to excluded directory;
- model-generated `../../` path;
- runtime executable spoof;
- secret-like text in model output;
- user says “sure” after an unrelated question;
- provider fails and another is available;
- agent attempts cross-project access;
- two proposed Rail roots;
- existing non-Workframe target directory.

## 9. Documentation deliverables during implementation

Implementation must maintain:

- protocol version and changelog;
- adapter support matrix;
- data-flow diagrams;
- grant vocabulary;
- schema references;
- security assumptions;
- fixture descriptions;
- known limitations;
- migration/integration decision log;
- exact evidence for claims of completion.

Do not claim “AI understands your computer” without defining the inspected scope, accepted doctrine, and verification evidence.

## 10. Campaign exit gates

The campaign may request canonical integration only when:

1. The read-only detector remains safe and compatible.
2. No model call occurs without explicit authorization.
3. Progressive scanning and private exclusions pass adversarial tests.
4. Formation is resumable and skips already grounded questions.
5. Teleology, ontology, and epistemology produce accepted durable files rather than form fields.
6. The planner can recommend no installation, a standalone project, or a larger profile correctly in fixtures.
7. Existing repositories can be adopted without movement or overwrite.
8. Rail uniqueness and agent authority validations pass.
9. A fresh runtime session can enter an installed project without full re-explanation.
10. Repository-only and Workframe-attached outcomes both work.
11. Accessibility fixtures pass.
12. Security review finds no unresolved critical grant, secret, path, or authority defect.
13. The implementation does not depend on private ABKB content.
14. The branch contains evidence sufficient to decide merge, experimental release, revision, or archive.
