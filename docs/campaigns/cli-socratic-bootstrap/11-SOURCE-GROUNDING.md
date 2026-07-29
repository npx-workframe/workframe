# Source Grounding and Campaign Decisions

## 1. Purpose

This file records which repository sources informed the campaign, which principles were retained, which source statements are historical or potentially conflicting, and which decisions came directly from the design transcript.

The campaign documents are a proposal. They do not convert referenced sources into shipped behavior.

## 2. Repositories reviewed

### Workframe

Repository: `npx-workframe/workframe`

Reviewed:

- `AGENTS.md`
- `START_HERE.md`
- `packages/workframe/README.md`
- `packages/workframe/package.json`
- `packages/workframe/bin/workframe.js`
- `docs/public/architecture.md`
- `docs/public/security.md`
- `docs/public/session-architecture.md`
- runtime-detection planning commits and release commit for the standalone CLI

### Architectonic main CLI

Repository: `architectonic/architectonic`

Reviewed:

- `README.md`
- `docs/INTEROPERABILITY.md`
- package metadata and command surface

### Architectonic layers

Repositories and reviewed files:

- `architectonic/constitution` — `README.md`
- `architectonic/doctrine` — `README.md`
- `architectonic/identity` — `README.md`
- `architectonic/project` — `README.md`
- `architectonic/knowledge` — `README.md`
- `architectonic/agents` — `README.md`
- `architectonic/rail` — `README.md`

### ABKB

Repository: `architectonic/abkb`

Reviewed:

- `README.md`
- `START_HERE.md`
- `knowledge/ontology/concepts.md`
- `projects/workframe/project_profile.md`
- `projects/architectonic/project_profile.md`
- `projects/architectonic/layers.md`

ABKB is private operating context. It is used only as a structural and doctrinal reference in this campaign. No private identity content, project secrets, or raw personal material is copied into the proposed product.

## 3. Workframe principles retained

### 3.1 Existing CLI is the correct bootstrap seed

The current standalone `workframe` CLI is explicitly a read-only local entrypoint. It detects installed runtimes and model-provider posture, can identify authenticated Codex status, and offers a consent-gated minimal inference test.

Campaign consequence:

- preserve `status` as read-only;
- extract detection into runtime adapters;
- extend the command surface through explicit formation states rather than turning status into an implicit installer.

### 3.2 Workframe is an execution and collaboration layer

Current Workframe architecture provides UI, authentication, rooms, vault, session binding, runtime profiles, approvals, files, and execution surfaces around Hermes.

Campaign consequence:

- Workframe Origin does not redefine Workframe as the canonical knowledge store;
- it attaches an Architectonic system to Workframe's operational surfaces;
- repository-only output remains valid.

### 3.3 Workframe does not replace the runtime

Current doctrine states that Workframe does not fork or replace Hermes. The campaign generalizes this runtime-neutral principle to Claude, Codex, Pi, and future adapters.

Campaign consequence:

- existing runtimes are invoked through bounded adapters;
- runtime-native authentication is used in place when possible;
- runtime session history remains execution state, not the highest source of truth.

### 3.4 Truth order

Current Workframe documentation states:

```text
Files > Kanban > Chat
```

Campaign consequence:

- approved Architectonic and project files preserve durable truth;
- Rail preserves live work state when needed;
- chat coordinates formation and execution but is not canonical doctrine.

### 3.5 Credential and runtime isolation

Current Workframe security separates the vault from runtime profiles, uses per-turn leases, supports BYOK and workspace funding, and distinguishes general egress from brokered secret-mediated actions.

Campaign consequence:

- raw secrets do not enter generated files or shared runtime mounts;
- model and funding policy are explicit per user/project/agent;
- use-in-place CLI authentication and Workframe vault credentials remain distinct modes;
- provider fallback is never silent.

### 3.6 Per-user runtime profiles and attribution

Current session architecture uses per-user runtime profiles and persists provider/model attribution for completed turns.

Campaign consequence:

- installed agents bind to explicit runtime profiles;
- project and organization permissions remain separate from runtime capability;
- receipts record which adapter and provider processed each bounded request.

## 4. Architectonic principles retained

### 4.1 Adaptive, smallest justified structure

Architectonic states that a disposable task may need no durable artifact, one concern may need one standalone layer, and compound profiles are justified only when concerns repeatedly interact.

Campaign consequence:

- the formation engine may recommend no installation;
- a standalone project must not be inflated into an organization;
- knowledge, living knowledge, agents, loops, graphs, and Rails require specific justification.

### 4.2 Local facts belong in local user-owned files

Architectonic installs replaceable upstream contracts while local facts, authority, decisions, projects, knowledge, and policy live in editable local files.

Campaign consequence:

- generated doctrine is local and user-owned;
- upstream package files and local accepted truth remain separate;
- model drafts are not canonical until accepted and written.

### 4.3 Document-guided onboarding

Architectonic describes onboarding as:

```text
inspect sources
-> classify facts, decisions, assumptions, contradictions, and unknowns
-> select the highest-value unresolved question
-> show the gap and consequence
-> record the explicit answer in its primary file
-> preserve unknowns
-> verify
-> stop when sufficiently grounded
```

Campaign consequence:

- the full Socratic script is evidence-led rather than a generic questionnaire;
- every material question has a source basis or explicit missing-evidence statement, consequence, and durable write target;
- the system does not ask for information already recoverable from authorized sources.

### 4.4 Access does not imply authority

Architectonic identity models actors, roles, authority, delegation, access, spending, mutation, privacy, and stopping boundaries. It explicitly is not a surveillance or personality-inference system.

Campaign consequence:

- scanning and operational authority are separate grants;
- identity remains collaboration-relevant rather than biographical;
- every installed agent requires a human owner, scope, grants, review, escalation, and stop authority.

### 4.5 Knowledge does not equal generated synthesis

Architectonic knowledge organizes disclosed claims, sources, evidence, uncertainty, contradictions, and known unknowns. Retrieval, embeddings, graphs, and generated summaries remain replaceable access paths.

Campaign consequence:

- source trails remain above generated summaries;
- evidence, decisions, assumptions, inferences, unknowns, contradictions, and staleness are distinct records;
- an evidence inventory is not a raw archive.

### 4.6 Project and Rail distinction

Architectonic Project states that a project is a bounded operating unit and that Rail coordinates live work only when it must cross sessions, roles, dependencies, review, or approval.

Campaign consequence:

- repository is not automatically project;
- project is not automatically subordinate to organization;
- each Rail-enabled project has one canonical ledger root;
- backlog, queue, now, board, and status are views rather than competing authorities.

### 4.7 Installed agents have no inherent authority

Architectonic Agents distinguishes public archetype, installed agent, and runtime agent. Installed files do not grant runtime authority.

Campaign consequence:

- agent bindings require owner, purpose, runtime, model policy, skills, knowledge, permissions, budgets, review, escalation, and stopping rights;
- Workframe enforcement, not prose alone, determines operational capability.

### 4.8 Workframe and Architectonic are complementary

Architectonic interoperability states:

```text
Architectonic  durable purpose, authority, projects, skills, knowledge, agents, upkeep
Workframe      execution, scheduling, claims, approvals, and runtime evidence
```

Campaign consequence:

- Workframe Origin composes the systems without making either mandatory for every outcome;
- Architectonic remains file-native and runtime-neutral;
- Workframe remains an optional but preferred persistent operating surface.

## 5. ABKB principles retained

### 5.1 Curated operating memory, not transcript dump

ABKB describes itself as a curated knowledge base for human-agent collaboration, not a raw archive, transcript dump, prompt pack, or generic wiki.

Campaign consequence:

- formation state does not become an unlimited chat archive;
- canonical outputs remain compact, classified, and source-grounded;
- private raw material stays at its source when references or extracts suffice.

### 5.2 Chain of truth

ABKB uses:

```text
memory or prior chat = hints
ABKB = curated index and operating context
source artifacts = truth
```

Campaign consequence:

- a runtime's hidden memory is never the authority;
- the generated Architectonic system routes agents to source artifacts;
- stale files and source freshness remain explicit concerns.

### 5.3 Knowledge classes

ABKB separates LLM-native, identity-native, project-native, skill-native, source-native, goal-native, and temporary context.

Campaign consequence:

- the formation engine classifies material before writing;
- identity and project knowledge require source review or explicit interview;
- temporary mood, shorthand, and conversational texture do not automatically become doctrine.

### 5.4 Read order and routing

ABKB provides a compact first-run route through constitution, role, project, skills, relevant identity/ontology, and then primary sources.

Campaign consequence:

- each installed workspace and project generates a concise `START_HERE.md`;
- runtime-specific adapters route to the same canonical files;
- agents do not load the entire knowledge base by default.

### 5.5 Instantiation reference

ABKB demonstrates a working system containing:

- runtime constitution;
- role registry;
- project profiles;
- source registries;
- ontology;
- skills and playbooks;
- goals;
- project-specific Rails and operating context;
- cross-runtime adapters.

Campaign consequence:

- the outcome example uses similar concern separation;
- the product does not assume ABKB's exact private directory names are universally correct;
- reusable principles flow upward, private content does not.

## 6. Source conflicts and historical boundaries

### 6.1 Workframe packaging language has evolved

The ABKB Workframe project profile contains historical packaging statements that predate or conflict with the current standalone `workframe` CLI release. Current repository source and package manifests outrank those historical descriptions.

Campaign decision:

- use the current standalone CLI as the bootstrap seed;
- treat ABKB Workframe packaging descriptions as historical context where inconsistent.

### 6.2 Architectonic layer order versus formation order

Current Architectonic package layers are organized as constitution, doctrine, identity, project, Rail, skills, knowledge, models, agents, meta, and living knowledge. The user explicitly prescribed a formation process beginning with teleology, then ontology, then epistemology, and continuing into doctrine, identity, constitution, projects, and execution.

Campaign decision:

- distinguish **formation order** from **storage/package order**;
- teleology is the first reasoning stage;
- current Architectonic `doctrine` may store declared purpose and governing principles;
- `teleology` remains a deprecated package alias and is not reintroduced as a mandatory package layer.

### 6.3 Current Workframe is Hermes-backed

Current Workframe product architecture is Hermes-backed. The campaign proposes runtime-neutral bootstrap adapters and potentially multiple runtime bindings.

Campaign decision:

- do not claim current Workframe already executes all listed runtimes;
- prototype runtime neutrality inside the isolated campaign;
- integrate only after adapter contracts and Workframe attachment behavior are proven.

## 7. Direct transcript decisions

The following campaign requirements came directly from the design discussion:

1. The system begins by recognizing installed agentic runtimes and model access.
2. It asks authorization before using an existing account, runtime, or key.
3. It may use existing auth in place, securely accept a key, or consider a bounded Workframe/OpenRouter-like fallback.
4. Deterministic logic is used when the problem is deterministic; model reasoning is used only when semantic judgment is required.
5. The first purpose classification allows multiple answers such as organization, business, and project.
6. The setup is teleology first, ontology second, epistemology third, followed by the other Architectonic concerns.
7. The system actively scans the machine and environment only with authorization.
8. It attempts to solve the practical philosophical problems: who am I, who is my user, what am I doing, how can I be useful, what is known, and what is unknown.
9. It must persist the result outside the chat.
10. It must “grill the user with docs” through a Socratic setup routine.
11. Questions about folders and files must be tied to a specific doctrinal concern; the system cannot merely save an import field.
12. The intended audience spans accessibility-first novices, skeptical professionals, moderately technical users, old-school programmers, and agentic power users.
13. The completed outcome includes customized organization, constitution, doctrine, team, projects, knowledge, agents, Workframe, runtime bindings, source attachments, repository organization, project Rails, and organization/project permission levels when justified.
14. This work is a separate construction campaign isolated from current Workframe and current Architectonic source state.
15. ABKB is a reference for what a mature instantiation can look like.

## 8. Derived campaign decisions

The following are architectural derivations made to implement the direct requirements:

- working product-mode name `Workframe Origin`;
- tagline `Your work should outlive the chat.`;
- progressive scan levels;
- structured grant authority;
- use-in-place runtime adapter preference;
- server-side hosted fallback rather than distributed shared key;
- formation state machine;
- evidence, claim, question, decision, entity, attachment, project, agent, transaction, and verification records;
- source attachment modes: reference, adopt, clone, mount read-only, mount read-write, copy snapshot, import extract;
- repository-only outcome alongside Workframe deployment;
- isolated prototype package before canonical integration;
- specific fixture personas and adversarial acceptance cases.

These are proposals and may be revised during implementation review.

## 9. Claim discipline

The campaign may claim that it **intends** to:

- reduce repeated context explanation;
- create portable user-owned context;
- bind multiple runtimes through adapters;
- conduct evidence-led Socratic formation;
- attach a customized Architectonic system to Workframe.

It may not claim these outcomes are demonstrated until implementation, fixture evidence, security tests, accessibility tests, and fresh-session continuity tests exist.

## 10. Review date and freshness

Sources were reviewed for this campaign on **2026-07-29**. Before implementation begins, the campaign operator must re-read current source heads, manifests, relevant ledgers, and package versions. This document is a source map, not a substitute for current repository inspection.
