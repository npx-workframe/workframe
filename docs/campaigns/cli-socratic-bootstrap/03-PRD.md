# Product Requirements Document

## Document status

- **Product:** Workframe Origin
- **Surface:** CLI-first; later wrappers may provide desktop and accessible graphical presentation
- **Campaign:** isolated from current Workframe implementation
- **Primary output:** customized Architectonic instance attached to a Workframe workspace and authorized runtimes
- **Canonical command concept:** `npx workframe`

## 1. Problem

Agentic runtimes are increasingly capable, but they usually enter each new session without a reliable, durable understanding of the user, entity, project, evidence, decisions, authority, privacy boundaries, and current work. Users repeatedly reconstruct the same context in chat. The resulting understanding is temporary, weakly sourced, difficult to inspect, and often trapped inside one provider.

The user's actual operating context already exists in fragmented form across:

- folders and documents;
- source-code repositories;
- notes and research;
- plans, task lists, and calendars;
- existing AI instructions and profiles;
- business and organizational records;
- personal working preferences;
- authenticated runtimes and development tools;
- explicit but undocumented knowledge held by the user.

Current installers treat the machine as a blank target. Current assistants treat the conversation as the primary context. Neither actively forms a durable, governed account of the user's world.

## 2. Vision

Create a consent-driven bootstrap system that safely discovers the user's environment, uses an authorized model only where semantic judgment is required, conducts an evidence-led Socratic formation process, and persists the result as a portable Architectonic system connected to Workframe and replaceable agent runtimes.

At completion, an authorized agent should be able to answer from explicit sources:

```text
Who am I?
Who is my user or owner?
What entity and project am I operating within?
To what end does it exist?
What is known, assumed, contradicted, stale, or unknown?
Which sources govern?
What may I access or change?
Which actions require approval?
What work is active?
How can I be useful now?
```

## 3. Product principles

1. **Teleology before tooling.** The system learns what the user is trying to accomplish before recommending a structure or runtime topology.
2. **Evidence before interview.** Inspect authorized documents before asking questions whose answers may already exist.
3. **Questions from gaps, not templates.** Ask about consequential ambiguities, contradictions, authority gaps, and unknowns.
4. **Files are canonical.** Chat coordinates formation; approved files and manifests preserve it.
5. **Access is not authority.** Every scope and effect requires an explicit grant.
6. **Progressive disclosure and permission.** Begin with low-risk metadata and request deeper access only when justified.
7. **Smallest justified Architectonic shape.** Install only layers the durable problem requires.
8. **Runtime neutrality.** Existing runtimes remain replaceable adapters.
9. **Deterministic mutations.** Models propose; validated transactions write.
10. **Portable exit.** The user can retain and use the resulting files without the bootstrapper or a specific provider.
11. **Accessible by default.** The experience must work for novice, skeptical, disabled, and expert users.
12. **Unknown is a valid result.** The system must not fabricate doctrine to satisfy completion percentages.

## 4. Personas

### P1 — Accessibility-first novice

- Uses a personal Windows machine with enlarged UI or assistive settings.
- Does not understand runtimes, repositories, providers, or file schemas.
- Needs one question at a time, plain language, reversible choices, and strong protection from accidental consent.
- Success: creates a useful personal or family project context without learning technical vocabulary.

### P2 — Skeptical regulated professional

- Uses a Mac or managed laptop.
- May be newly willing to try AI but is concerned about confidentiality, professional ethics, and data transmission.
- Needs explicit private zones, local-only options, source-by-source approval, and clear statements of what reaches external providers.
- Success: receives useful assistance on safe domains while protected data remains explicitly excluded.

### P3 — Technically capable but agentically non-current user

- Understands software and folders but not current agent runtimes, skills, profiles, context architectures, or model-provider differences.
- Wants sensible recommendations with explanations.
- Success: uses an existing authenticated runtime and receives a coherent project or business workspace without manual integration.

### P4 — Old-school programmer and machine owner

- Maintains a highly customized computer and distrusts opaque installers.
- Wants exact paths, commands, process boundaries, manifests, diffs, logs, rollback, and no silent changes.
- Success: can inspect and approve every operation and retain existing layout and tools.

### P5 — Agentic power user

- Already operates multiple models, CLIs, repositories, agents, skills, or VPS environments.
- Wants direct control over adapters, mounts, profiles, funding policy, agents, and project boundaries.
- Success: consolidates existing systems into a durable organizational contract without losing runtime flexibility.

## 5. Jobs to be done

### Primary job

> When I begin using an AI agent, help me turn what already exists on my machine and in my head into a durable, structured context so that future agents can continue the work without requiring me to explain everything again.

### Supporting jobs

- Discover which agentic runtimes and providers are already usable.
- Explain and obtain permission to use one inference path.
- Identify likely projects and organizations without reading everything by default.
- Separate personal, professional, organizational, public, confidential, and excluded information.
- Detect contradictions between documents and current intent.
- Record facts, decisions, assumptions, and unknowns distinctly.
- Organize existing repositories and folders without destroying their native structure.
- Define who and what agents may access, change, publish, spend, or execute.
- Establish durable current-work state with one Rail per project when required.
- Deploy or connect a Workframe surface.
- Resume formation or operation after interruption.

## 6. End-to-end user journey

### Stage 1 — Start

The user runs `npx workframe`, a signed native executable, or a future desktop wrapper. The system detects accessibility and terminal capabilities and offers a simple or detailed presentation mode.

### Stage 2 — Read-only preflight

The CLI detects:

- platform and architecture;
- Node, Git, Docker, shells, editors, and supported substrates;
- supported agentic runtime executables and safe version information;
- authenticated status only through documented, non-mutating commands;
- provider environment posture without printing values;
- existing Architectonic manifests;
- existing Workframe installations;
- likely project roots and repository locations using metadata-only discovery after permission.

No model call or file mutation occurs.

### Stage 3 — Inference authorization

The system presents available inference paths in priority order:

1. existing authenticated runtime used in place;
2. existing environment key used in place;
3. user supplies a provider key for local vault storage;
4. tightly metered Workframe-hosted relay;
5. deterministic-only mode.

The user sees the provider, funding source, expected scope, data path, and revocation method before approval.

### Stage 4 — Evidence authorization

The system requests progressively deeper access:

1. named root locations and metadata;
2. folder and repository inventory;
3. file names, types, sizes, and modification metadata;
4. selected file contents processed locally;
5. selected excerpts sent to an external model;
6. approved writes, copies, clones, or mounts.

The user may exclude paths or declare local-only/private zones at any step.

### Stage 5 — Formation

The Socratic process follows the campaign formation order:

1. teleology;
2. ontology;
3. epistemology;
4. doctrine and values;
5. identity, authority, delegation, and privacy;
6. constitution and invariants;
7. project boundaries and success conditions;
8. knowledge, skills, agents, and model policy;
9. Rail and work-selection rules;
10. Workframe deployment and runtime binding;
11. upkeep, audit, and completion.

At each stage, the system first inspects approved sources, classifies evidence, and asks the highest-value unresolved question.

### Stage 6 — Plan

The CLI shows:

- proposed Architectonic layers and why each is justified;
- proposed organization and project tree;
- proposed source attachments and their modes;
- proposed repository clones or references;
- proposed Rails;
- proposed agents, runtime bindings, tools, knowledge attachments, and permissions;
- proposed Workframe deployment mode;
- exact file writes and commands;
- secrets and data-flow implications;
- rollback plan.

### Stage 7 — Apply

Approved changes execute as deterministic transactions. Existing paths are never overwritten silently. Each mutation is logged, validated, and reversible where feasible.

### Stage 8 — Verify and enter workspace

The system validates:

- Architectonic manifest and installed layer closure;
- canonical file presence and schema compliance;
- source attachment provenance;
- project-to-Rail bindings;
- agent ownership and authority records;
- provider and runtime bindings;
- Workframe health and session binding;
- permission enforcement;
- startup context for each agent.

The user then enters Workframe or receives a repository-only outcome.

## 7. Functional requirements

### FR-01 — Environment discovery

The product must detect supported runtimes and substrates through allowlisted probes. It must distinguish `missing`, `detected`, `verified`, `authenticated`, `configured`, `unsupported`, and `unknown` without exposing secrets.

### FR-02 — Runtime adapter registry

Each runtime adapter must declare:

- discovery commands;
- authentication-status probe;
- supported invocation modes;
- whether prompts or files may be passed;
- sandbox and permission controls;
- cancellation behavior;
- cost/funding implications;
- evidence and receipt capability;
- unsupported or unsafe operations.

### FR-03 — Explicit inference consent

No model call may occur without a recorded grant that names the adapter/provider, scope, funding path, data class, and expiry or revocation behavior.

### FR-04 — Credential safety

The product must use authenticated CLIs in place when possible. It must not scrape private token stores, browser caches, shell history, or arbitrary `.env` files. User-supplied API keys may be imported only through a secure input path and stored in the Workframe vault or an explicitly selected local secret store.

### FR-05 — Progressive scanner

The scanner must support separately authorized levels:

- root discovery;
- folder inventory;
- repository inventory;
- file metadata;
- local content extraction;
- externally processed excerpts;
- mutation and attachment.

It must support explicit exclusions, size limits, file-type allowlists, ignore rules, and local-only classifications.

### FR-06 — Evidence classification

The system must classify candidate material as:

- fact-bearing source;
- explicit decision;
- assumption;
- inference;
- open question;
- contradiction;
- stale or superseded source;
- temporary context;
- sensitive or excluded material.

Probabilistic classifications remain proposals until validated or accepted.

### FR-07 — Socratic question selection

The formation engine must select questions by consequence and unresolved value, not by a fixed checklist. It must avoid asking for information recoverable from authorized sources and must show the evidence gap or contradiction that motivates each nontrivial question.

### FR-08 — Formation persistence

The setup must be resumable. It must persist grants, source references, evidence classifications, asked questions, explicit answers, decisions, proposed writes, applied transactions, verification results, and remaining unknowns.

### FR-09 — Architectonic planning

The deterministic planner must map durable concerns to the smallest justified Architectonic layer or profile. It must be able to recommend no layer, one standalone layer, or a composed profile.

### FR-10 — Architectonic materialization

Approved doctrine must be written into human-readable canonical files. The system must distinguish generated drafts from accepted local truth. Files must include provenance where relevant.

### FR-11 — Source attachment modes

The product must support:

- `reference`: record a path or URL without filesystem integration;
- `mount_read_only`: expose an existing folder without copying or mutation;
- `mount_read_write`: expose an existing folder with explicit mutation authority;
- `copy_snapshot`: copy selected material with source and timestamp provenance;
- `clone_repository`: clone a Git repository into an approved location;
- `adopt_existing_repository`: bind an existing checkout without moving it;
- `import_extract`: store selected normalized excerpts rather than the raw source.

### FR-12 — Repository-to-project organization

The product must allow one project to contain multiple repositories and one repository to participate in a larger organization. It must not assume repository equals project.

### FR-13 — Rail binding

A project receives one Rail only when work must persist across sessions, roles, dependencies, review, or approval. The project contract must name the single `ledger_root`. The system must reject competing live-work ledgers.

### FR-14 — Agent installation and binding

An installed agent record must specify:

- human owner;
- purpose and role;
- organization and project scope;
- runtime adapter and profile;
- model policy and funding policy;
- tools and skills;
- knowledge attachments;
- filesystem access;
- external-action authority;
- spending limits;
- approval and review gates;
- escalation and stop authority;
- Rail selection rules;
- evidence and handoff requirements.

### FR-15 — Workframe deployment

The product must support at least:

- repository-only outcome;
- local single-user Workframe;
- local trusted-team Workframe;
- existing remote Workframe attachment;
- new VPS or remote deployment as a later gated capability.

### FR-16 — Verification

The system must verify structural correctness, permission bindings, source provenance, project-to-Rail uniqueness, agent authority completeness, runtime readiness, and Workframe health before declaring completion.

### FR-17 — Revocation and detach

The user must be able to revoke inference grants, disable runtime adapters, detach sources, remove mounts, rotate imported credentials, and archive or delete formation state without corrupting canonical project files.

### FR-18 — Explainability

Every recommendation must be inspectable as:

```text
observed evidence
+ explicit user decisions
+ deterministic rules
+ labeled model inference
= proposed action
```

## 8. Non-functional requirements

### NFR-01 — Accessibility

- Respect terminal and OS accessibility settings where observable without invasive probing.
- Support large-print and high-contrast presentation.
- Ask one primary question at a time in simple mode.
- Do not require mouse precision.
- Provide clear undo, repeat, explain, skip, pause, and exit commands.
- Never use ambiguous default consent for sensitive actions.

### NFR-02 — Privacy

- Default to local processing.
- Do not transmit inventory or content without a separate grant.
- Redact private paths and identifiers in logs and support bundles.
- Never log secret values.

### NFR-03 — Portability

Canonical outputs must be ordinary files and documented schemas. A user must be able to open, version, copy, or migrate them independently.

### NFR-04 — Resilience

Formation must survive interruption, model failure, runtime unavailability, partial installation, and process restart. Applied transactions must be distinguishable from proposed operations.

### NFR-05 — Performance

Metadata inventory must be bounded by scope, ignore rules, and budgets. The system must avoid whole-disk content indexing by default.

### NFR-06 — Security

Commands, paths, and model-produced arguments must be validated against allowlists and schemas. No probabilistic output may become a shell command or file mutation without deterministic compilation.

### NFR-07 — Auditability

The user must be able to inspect what was discovered, what was transmitted, what was inferred, what was confirmed, what was written, and which adapter performed each operation.

## 9. Initial release scope

### Included

- current Workframe CLI runtime discovery extracted into adapters;
- consent records;
- use-in-place support for at least Codex CLI and Claude Code;
- one provider-key path;
- deterministic-only fallback;
- metadata-first scanner for user-selected roots;
- local Markdown and common text/code formats;
- resumable formation state machine;
- teleology, ontology, epistemology, doctrine, identity, constitution, project, and knowledge formation;
- Architectonic plan and local installation;
- existing-repository adoption;
- one project Rail binding;
- local single-user Workframe attachment or repository-only outcome;
- verification and revocation.

### Deferred

- unrestricted email, cloud-drive, browser-history, or calendar ingestion;
- autonomous whole-disk scanning;
- medical, legal, or financial domain certification;
- public multi-user hosted service as the default;
- automatic paid VPS procurement;
- automatic publication or outbound communication;
- hidden behavioral profiling;
- universal runtime support;
- opaque long-term platform memory.

## 10. Success metrics

### Activation

- Percentage of users who complete runtime authorization.
- Percentage who reach a verified Architectonic plan.
- Percentage who finish with at least one grounded entity or project.

### Continuity

- Percentage of subsequent sessions that load the correct project context without a full re-explanation.
- Reduction in repeated onboarding explanation time.
- Percentage of agent actions linked to explicit project, authority, and source context.

### Quality

- Number of preserved unknowns versus silently invented fields.
- Percentage of accepted claims with provenance.
- Rate of user correction to model-proposed classifications.
- Number of detected and resolved source contradictions.

### Safety

- Unauthorized model calls: zero.
- Secret values written to logs: zero.
- Content transmitted outside granted scope: zero.
- Silent overwrite of existing paths: zero.
- Projects with multiple canonical live-work ledgers: zero.
- Installed agents without owners and authority records: zero.

### Usability

- Completion rate by novice and expert modes.
- Accessibility task success at high zoom and keyboard-only operation.
- Percentage of users who can correctly explain what was scanned and what was sent externally.

## 11. Non-goals

Workframe Origin is not intended to:

- infer a complete psychological profile;
- ingest a person's whole life by default;
- replace source repositories with generated summaries;
- make legal or ethical decisions on the user's behalf;
- prove that declared doctrine is true, wise, safe, or lawful;
- guarantee that a model follows instructions perfectly;
- create an organization when a project is sufficient;
- create a Rail for disposable work;
- grant agents authority because they were installed;
- replace Claude, Codex, Hermes, or other runtimes;
- force Workframe deployment when a repository-only outcome is sufficient.

## 12. Release acceptance summary

The first release is acceptable when a fresh user can:

1. run the CLI on a supported machine;
2. see which runtimes and inference paths were detected;
3. authorize one path or remain deterministic-only;
4. grant metadata access to selected locations;
5. identify an organization, business, project, or personal system through natural dialogue;
6. allow selected documents to inform teleology, ontology, and epistemology;
7. review and approve a customized Architectonic plan;
8. attach at least one existing repository or folder without destructive movement;
9. create and validate one project Rail when justified;
10. bind one agent with explicit owner, runtime, permissions, and project scope;
11. enter a local Workframe or repository-only result;
12. start a new session that correctly loads the persisted context;
13. inspect and revoke the permissions used to create it.
