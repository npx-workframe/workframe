# Full Socratic Setup Script

## 1. Script purpose

This is the adaptive formation tree for Workframe Origin. It is not intended to be rendered as one long questionnaire. The orchestrator enters the tree at the relevant node, inspects authorized evidence before asking, asks one primary question at a time, persists approved outcomes, and skips branches that are already resolved or not justified.

## 2. Notation

```text
[D] deterministic operation
[P] probabilistic interpretation or draft
[U] explicit user choice or answer
[G] permission grant
[W] durable write target
[V] verification gate
[!] material warning or consequence
[STOP] safe stopping point
[LOOP] repeat only while unresolved value remains
```

Every probabilistic result remains a proposal until it passes deterministic validation and the required user or authority gate.

## 3. Root tree

```text
ROOT — begin Workframe Origin
|
+-- 0. Presentation and accessibility
|   +-- determine interaction mode
|   +-- confirm language, pace, and explanation level
|   +-- establish stop/back/repeat controls
|
+-- 1. Read-only environment preflight
|   +-- discover host and supported substrates
|   +-- discover runtimes and provider posture
|   +-- discover existing Architectonic/Workframe markers
|   +-- report without mutation or model call
|
+-- 2. Inference authorization
|   +-- use authenticated runtime in place
|   +-- use existing provider environment in place
|   +-- securely add a user key
|   +-- use bounded Workframe-funded relay
|   +-- continue deterministic-only
|
+-- 3. Progressive evidence authorization
|   +-- identify candidate roots
|   +-- inventory names and metadata
|   +-- select private/excluded zones
|   +-- inspect selected contents locally
|   +-- approve exact excerpts for external inference
|
+-- 4. Teleology — to what end?
|   +-- select goal classes
|   +-- determine intended outcome and beneficiary
|   +-- define success, priority, horizon, and non-outcomes
|   +-- decide whether durable installation is justified
|
+-- 5. Ontology — what exists?
|   +-- identify entity candidates
|   +-- separate person, organization, business, project, and source
|   +-- map actors, projects, repositories, systems, and boundaries
|   +-- preserve unresolved classifications
|
+-- 6. Epistemology — what is known and how?
|   +-- identify governing sources
|   +-- classify facts, decisions, assumptions, inferences, unknowns
|   +-- detect contradictions and staleness
|   +-- define acceptance and correction rules
|
+-- 7. Doctrine and values — how should judgment work?
|   +-- derive principles from real trade-offs
|   +-- define evidence, risk, method, and incentives
|   +-- identify when not to act
|
+-- 8. Identity, authority, delegation, and privacy
|   +-- identify owner and human authority root
|   +-- define roles and responsibilities
|   +-- define access, mutation, publishing, spending, and stop rights
|   +-- define private and local-only zones
|
+-- 9. Constitution and governance
|   +-- state non-negotiable invariants
|   +-- prohibit actions
|   +-- establish amendment and override rules
|   +-- define composition boundaries
|
+-- 10. Projects, sources, repositories, and Rails
|   +-- define each bounded project
|   +-- attach repositories and folders
|   +-- choose reference/mount/copy/clone modes
|   +-- create one Rail where durable coordination is justified
|
+-- 11. Knowledge, skills, agents, models, and loops
|   +-- define knowledge domains and source trails
|   +-- select reviewed skills only when needed
|   +-- install agents with explicit owners and permissions
|   +-- bind runtimes, models, funding, review, and stop conditions
|
+-- 12. Workframe outcome
|   +-- repository-only
|   +-- local single-user
|   +-- local trusted team
|   +-- attach existing Workframe
|   +-- gated remote deployment
|
+-- 13. Plan, apply, verify, and enter
|   +-- show proposed structure and exact changes
|   +-- resolve material objections
|   +-- apply deterministic transactions
|   +-- verify files, Rails, permissions, runtimes, and workspace
|   +-- generate next-session entry context
|
+-- 14. Upkeep and resumption
    +-- persist formation state
    +-- define review triggers
    +-- revoke or detach
    +-- resume unresolved formation later
```

---

## 4. Node 0 — presentation and accessibility

```text
0.0 [D] Detect terminal capabilities without personal profiling
|
+-- interactive TTY available
|   +-- continue
|
+-- non-interactive environment
|   +-- output status/plan only
|   +-- require explicit flags for mutation
|
+-- screen reader / high contrast / large-print mode requested
    +-- use one question per screen
    +-- no decorative animation
    +-- explicit numbered choices plus natural-language input
```

Primary prompt:

> Before we begin, how should I present this setup?
>
> 1. Simple: one question at a time, plain language  
> 2. Guided: recommendations with explanations  
> 3. Detailed: show paths, commands, data flows, and schemas  
> 4. Tell me in your own words

Follow-up branches:

```text
[U] simple
  -> never show raw JSON unless requested
  -> explain technical terms inline
  -> ask explicit yes/no for every sensitive grant

[U] guided
  -> show recommendation and consequence
  -> allow "explain more" before consent

[U] detailed
  -> show probes, paths, adapter names, and exact proposed writes

[U] custom
  -> [P] interpret presentation preferences
  -> [D] compile to supported renderer settings
```

Mandatory control message:

> You can say **back**, **repeat**, **explain**, **skip**, **pause**, or **stop** at any time. Stopping does not delete what you have already approved. Nothing sensitive is scanned or sent merely because setup has started.

`[W] .workframe-origin/formation.json -> presentation`

---

## 5. Node 1 — read-only environment preflight

### 1.0 Initial disclosure

> I will first check basic system information and whether supported AI runtimes are already installed. This step uses fixed local checks. It does not read your documents, reveal credential values, call a model, or change your machine.

```text
1.1 [D] Probe host
  -> OS, architecture, shell, Node, npm, Git, Docker

1.2 [D] Probe supported runtimes
  -> Hermes
  -> Codex CLI
  -> Claude Code
  -> Pi
  -> OpenClaw
  -> Cursor Agent
  -> other registered adapters

1.3 [D] Probe safe auth posture
  -> documented status commands only
  -> no private token-store parsing

1.4 [D] Probe provider posture
  -> presence of allowlisted environment variable names
  -> never print values

1.5 [D] Probe existing installations
  -> Architectonic manifest markers
  -> Workframe install markers
  -> no recursive content read
```

Report format:

```text
I found:
- Claude Code: installed, authentication status available
- Git: installed
- Docker: installed, engine unavailable
- Architectonic: no confirmed installation in the current directory
- Workframe: no confirmed installation in the current directory

I did not inspect your documents or send anything anywhere.
```

Branches:

```text
runtime found
  -> node 2

no runtime, provider marker found
  -> node 2 provider path

nothing usable found
  -> offer user key, hosted relay, or deterministic-only

existing Architectonic found
  -> offer reopen, inspect, extend, or create separate instance
  -> never overwrite

existing Workframe found
  -> offer attach, inspect, or create separate workspace
```

`[W] .workframe-origin/audit/preflight.json`

---

## 6. Node 2 — inference authorization

### 2.0 Explain the distinction

> I can continue with fixed rules only, but an authorized language model is useful for understanding documents, detecting contradictions, and asking better questions. Detecting a model or account does not authorize me to use it.

### 2.1 Existing authenticated runtime branch

Example:

> Claude Code appears to be installed and authenticated. May I use it during formation?
>
> It would receive only the text you explicitly approve for model processing. It may consume usage from your existing Claude account. I will use its supported command interface; I will not copy its private authentication files.

```text
[U] yes
  -> [G] inference.use:claude-cli
  -> choose default data classes: answers only / approved excerpts / broader selected sources
  -> run optional minimal verification call

[U] no
  -> retain adapter as detected but unauthorized
  -> show next path

[U] explain
  -> show exact invocation boundary, cost source, and revocation
```

Equivalent branches exist for Codex, Hermes, Pi, and future adapters.

### 2.2 Existing provider environment branch

> I found that `OPENROUTER_API_KEY` is set in this process environment. I cannot see or display the key through this setup. May I use it for approved formation requests?

```text
[U] use in place
  -> [G] inference.use:openrouter-env
  -> no key import

[U] import to Workframe vault
  -> explain storage, encryption, deletion, and future use
  -> [G] credential.store:openrouter
  -> secure deterministic import

[U] do not use
  -> mark unavailable by user choice
```

### 2.3 New user key branch

> You can add your own provider key. The key will be entered through a hidden input and stored only in the location you approve. Do not paste it into ordinary chat.

```text
[U] add key
  -> choose provider
  -> choose environment-only or Workframe vault
  -> secure input
  -> validation request only after approval

[U] skip
  -> hosted relay or deterministic-only
```

### 2.4 Workframe-funded relay branch

> No local inference path is available. Workframe may provide a small, metered setup allowance through a server-side relay. Approved text would be sent to the selected provider through Workframe. The allowance is limited to formation and can be revoked.

Must disclose:

- provider and model class;
- data sent;
- retention statement;
- session budget;
- rate limit;
- funded-by-Workframe status;
- no shared key delivered to the client.

### 2.5 Deterministic-only branch

> We can continue without a language model. I can discover runtimes, inventory selected paths, install explicit Architectonic profiles, and ask a fixed minimum set of questions. I will not attempt semantic contradiction analysis.

`[W] .workframe-origin/grants.json`  
`[W] .workframe-origin/audit/inference-receipts.jsonl`

---

## 7. Node 3 — progressive evidence authorization

### 3.0 Establish private zones first

> Before looking for projects, are there places this setup must never inspect?
>
> You can name folders, accounts, categories, or say things such as “patient records,” “family photos,” “tax files,” or “anything under this path.”

```text
[U] explicit paths
  -> [D] normalize and store exclusion scopes

[U] categories
  -> [P] propose candidate path rules
  -> [U] confirm exact rules before enforcement

[U] none known
  -> continue; still stop on sensitive-path heuristics
```

### 3.1 Candidate-root discovery

> I can look for likely work locations by checking only names and basic metadata in the places you select. I will not read file contents yet.

Suggested roots are OS-specific and shown explicitly:

```text
Documents
Desktop
user-selected project folder
known Git workspace roots
cloud-sync root if locally available
current directory
other path supplied by user
```

```text
[U] select roots
  -> [G] filesystem.inventory:<root> at metadata level
  -> [D] bounded inventory

[U] choose folder manually
  -> use native selector or typed path

[U] no scan
  -> user may describe or select exact files later
```

### 3.2 Inventory review

The system presents candidates, not conclusions:

```text
Possible active work areas:
- ~/Projects/clinic-site         Git repository, modified recently
- ~/Documents/Seminar            documents and slides
- ~/Projects/old-experiment      Git repository, no recent changes

These are candidates based on metadata only. I have not decided that they are projects.
```

Question:

> Which of these should help define what you are doing now?

Branches per candidate:

```text
active and relevant
archival reference
belongs to another person/client
private/excluded
not a project but useful source
uncertain
ignore
```

### 3.3 Content access

For each formation concern, request exact sources:

> We are trying to understand the purpose of the seminar project. I found `README.md`, `seminar-outline.docx`, and `notes/why-this-matters.md`. May I read these locally for this purpose?

```text
[U] approve all listed
  -> [G] local content read for exact files

[U] approve subset
  -> restrict scope

[U] local only
  -> extraction and local classification only
  -> no external model transmission

[U] allow approved excerpts to model
  -> [G] inference.transmit for exact evidence IDs

[U] decline
  -> ask user directly or preserve unknown
```

### 3.4 Universal evidence branch

At any formation node:

> I am defining **<specific concern>**. The current evidence is incomplete because **<gap or contradiction>**.
>
> Which folders, files, repositories, or other sources should help define this aspect? I will first show what I intend to inspect and why.

This question must always name the concern. The system must not ask for broad import merely to increase coverage.

`[W] sources/attachments.json`  
`[W] .workframe-origin/evidence.json`

---

## 8. Node 4 — teleology

### 4.0 Goal-class entry

> What best describes what you are trying to establish? Choose any that apply, or answer naturally.
>
> - Start an organization  
> - Start a business  
> - Start a project  
> - Build a personal knowledge system  
> - Form an agent team  
> - Organize work that already exists  
> - Something else

```text
[U] one or more choices
  -> [P] translate into candidate concerns, not final layers
  -> inspect approved evidence for purpose claims
```

### 4.1 Evidence-led purpose synthesis

```text
[D] gather approved purpose-bearing sources
[P] extract candidate purpose claims
[P] identify conflict, ambiguity, or missing beneficiary/outcome
[D] classify as proposals
```

Example question:

> Your website describes a consulting practice, while your recent planning notes describe a software product. Is the current purpose:
>
> 1. operate both as separate lines,  
> 2. transition from consulting to software,  
> 3. use consulting to fund the software project, or  
> 4. something else?

### 4.2 Beneficiary

> Who should be better off if this succeeds?

Branches:

```text
self
family or household
clients/customers
patients or protected beneficiaries
team or organization
public/community
another identified group
multiple groups with possible conflict
```

If multiple groups conflict:

> When their interests conflict, whose interest governs, and under what condition?

### 4.3 Success evidence

> What would let you say this has worked—not merely that activity occurred?

The system may offer evidence-derived candidates but must label them:

```text
revenue or sustainability
completed deliverable
reduced workload
improved quality or access
maintained privacy or safety boundary
adoption or usage
learning or clarity
other observable state
```

### 4.4 Non-outcome

> What result would look like progress but actually violate the point of the effort?

This can identify anti-goals such as growth that sacrifices confidentiality, automation that removes human judgment, or a sophisticated system nobody can maintain.

### 4.5 Priority and horizon

> Which purpose matters now, and which can remain secondary?

> What time horizon should guide the initial system: today, this month, this year, or ongoing?

### 4.6 Durability gate

```text
purpose is disposable and one-session
  -> recommend no Architectonic installation
  -> offer plain task assistance

one durable bounded concern
  -> candidate standalone layer/project

several interacting durable concerns
  -> continue formation
```

`[W] organization/PURPOSE.md or project purpose target`  
`[W] goals/<goal>.md when an explicit goal contract is justified`

---

## 9. Node 5 — ontology

### 5.0 Candidate entity map

The system shows hypotheses:

```text
I currently see these possible entities:
- you as an individual operator
- a professional practice
- an education project
- two source-code repositories
- a document collection used by both projects

These are provisional. Which are separate things, and which belong together?
```

### 5.1 Person versus entity

> Should this context belong to you personally, to an organization, to a business, to a project, or to several separate scopes?

If same human, multiple roles:

> Which information belongs to you personally, and which belongs only to your professional role or organization?

### 5.2 Organization/business distinction

```text
business selected
  -> ask whether there is a durable organization boundary
  -> identify commercial purpose, customers, offer, revenue model, constraints
  -> do not create separate foundational "business" layer automatically

organization selected
  -> identify members, authority, projects, boundaries, and upkeep

project only
  -> keep standalone unless governance concern is material
```

### 5.3 Project versus repository

For each repository:

> Is `<repo>`:
>
> 1. the whole project,  
> 2. one component of a larger project,  
> 3. a reusable dependency,  
> 4. an archive or source, or  
> 5. uncertain?

### 5.4 Actor map

> Who or what participates in this system?

Classify:

```text
human owner
human collaborator
client/customer/beneficiary
external authority
team
agent archetype
installed agent
runtime process
service or integration
```

### 5.5 Relationship confirmation

The system proposes a tree or graph and asks targeted questions:

> I have placed the education project under the professional practice because both sources use the same brand. Your notes also discuss separating them. Should they share governance, share only selected knowledge, or remain independent?

### 5.6 Ontology write

`[W] organization/IDENTITY.md`  
`[W] organization/people/`  
`[W] organization/teams/`  
`[W] projects/<project>/project_profile.md`  
`[W] workspace/project registry`

Unresolved classification becomes an explicit open question rather than a forced tree edge.

---

## 10. Node 6 — epistemology

### 6.0 Source authority map

> Which sources should govern when they disagree?

Evidence-derived presentation:

```text
- signed agreement: formal but limited to client scope
- current repository README: maintained by project team
- private planning note: recent but provisional
- website: public but possibly outdated
- your answer today: explicit current decision
```

The user may define scope-specific authority rather than one global ranking.

### 6.1 Claim classification review

The system presents a small set of high-impact claims:

```text
Claim: "The initial customer is independent clinics."
Source: pitch deck, modified 2026-06-12
Classification proposal: prior decision, current status uncertain

Is this current, superseded, still an assumption, or unknown?
```

### 6.2 Contradiction loop

```text
[LOOP]
  [P] rank contradictions by consequence
  [D] ensure evidence scope is authorized
  ask one question
  record resolution, scope split, supersession, or unresolved state
  stop when remaining contradictions do not block safe operation
```

Example:

> The README says agents may publish independently, while your security notes require approval for all external communication. Which rule governs now?

### 6.3 Staleness

> Which parts of this knowledge can become wrong because the outside world changes?

Branches:

```text
changes only through deliberate local decisions
  -> ordinary knowledge

changes on external clock
  -> consider living knowledge only after watch and verification rules exist
```

### 6.4 Correction policy

> Who may correct facts, change decisions, resolve contradictions, or retire sources?

### 6.5 Epistemology write

`[W] organization/KNOWLEDGE.md` or knowledge corpus contract  
`[W] projects/<project>/sources.md`  
`[W] decisions.md`  
`[W] assumptions.md`  
`[W] open_questions.md`  
`[W] contradiction records`

---

## 11. Node 7 — doctrine and values

### 7.0 Derive doctrine from trade-offs

Do not ask for a list of admirable words. Search for actual recurring choices.

> Your sources repeatedly choose speed over formal process, but they also require independent review before release. Is the rule “move quickly until an external or irreversible boundary is reached,” or is another principle more accurate?

### 7.1 Evidence standard

> What level of evidence is required before the system may:
>
> - treat a claim as current;  
> - recommend a decision;  
> - change a project file;  
> - publish externally;  
> - spend money;  
> - make a destructive change?

### 7.2 Risk posture

> Which failures are tolerable, reversible, or unacceptable?

### 7.3 Method

> When the path is uncertain, should agents prefer experimentation, further research, user questioning, conservative inaction, or a scoped combination?

### 7.4 Incentives

> What should the system optimize, and what apparent optimization would create the wrong behavior?

### 7.5 Stop doctrine

> Under what conditions should an agent stop rather than continue trying?

`[W] organization/DOCTRINE.md`  
`[W] project-specific doctrine when the rule is local`

---

## 12. Node 8 — identity, authority, delegation, and privacy

### 8.0 Human authority root

> Who has final authority over this system?

For a single-user setup, this is usually the user. For an organization, authority may be scoped.

### 8.1 Role formation

For each recurring role:

```text
role purpose
responsibilities
inputs
outputs
allowed decisions
required approvals
escalation
stop authority
```

Question:

> Which responsibilities recur often enough to deserve a durable role rather than being handled ad hoc?

### 8.2 Permission dimensions

For each human or agent:

```text
read
write
execute
install
connect credentials
publish
message externally
spend
create agents
change permissions
approve
override
stop
```

Question example:

> The research agent needs broad web access and read access to the project sources. Does it need permission to edit canonical project files, or should it submit evidence for another role to reconcile?

### 8.3 Privacy domains

> Which information is:
>
> - public;  
> - internal;  
> - confidential;  
> - local-only;  
> - prohibited from AI processing;  
> - permitted only for a specific runtime or provider?

### 8.4 Delegation

> May agents delegate work to other agents? If yes, may they grant only a subset of their own permissions, and who approves new agent creation?

Default: no agent may delegate more authority than it holds; creation and high-impact grants require a human or designated admin gate.

### 8.5 Spending and funding

> Which inference or external service costs may be paid by the user, the workspace, a project budget, or nobody without approval?

### 8.6 Identity and authority write

`[W] organization/IDENTITY.md`  
`[W] organization/AUTHORITY.md`  
`[W] organization/PRIVACY.md`  
`[W] role and permission records`  
`[W] grants.json`

---

## 13. Node 9 — constitution and governance

### 9.0 Invariants

> What must remain true even if the projects, models, agents, or tactics change?

Evidence-derived candidate examples:

```text
human retains stop authority
patient-identifiable data never reaches external AI
no external publication without approval
canonical sources remain user-owned
no agent may grant itself new permissions
```

### 9.1 Prohibited actions

> Which actions are forbidden rather than merely approval-gated?

### 9.2 Amendment

> Who may amend the constitution, and what evidence or review is required?

### 9.3 Emergency override

> Is any emergency override allowed? Who may invoke it, how is it recorded, and which prohibitions remain absolute?

### 9.4 Composition

> When personal, organizational, project, or client rules conflict, which scope governs and where must the boundary remain separate?

`[W] organization/CONSTITUTION.md`

---

## 14. Node 10 — projects, sources, repositories, and Rails

### 10.0 Project candidates

The system proposes projects only from accepted ontology and purpose:

```text
Possible projects:
- professional seminar
- practice operations improvement
- public website
- personal knowledge organization
```

Question:

> Which of these are active bounded projects, which are ongoing responsibilities, and which are merely source collections?

### 10.1 Project contract

For each project, establish:

```text
purpose
scope
exclusions
users/beneficiaries
owner
canonical sources
repositories
current state
success evidence
risks
assumptions
unknowns
handoff rule
```

### 10.2 Attachment mode

For each source folder/repository:

> How should Workframe use `<source>`?
>
> 1. Reference it where it is  
> 2. Attach it read-only  
> 3. Attach it with approved write access  
> 4. Copy a dated snapshot  
> 5. Clone the repository into the new workspace  
> 6. Import selected extracts only  
> 7. Do not attach it

Show consequences before approval.

### 10.3 Repository organization

If multiple repositories:

> These repositories appear to support one project. Should they remain independent checkouts attached to the same project, or should the setup create a parent workspace that contains clones of them?

Never move existing checkouts without explicit destructive authorization.

### 10.4 Rail gate

> Will this project’s work need to survive more than one session, coordinate more than one role, track dependencies, require review, or wait for approval?

```text
no
  -> no Rail
  -> project documents and session handoff are sufficient

yes
  -> create exactly one operations/ledger.json
  -> define roles, selection rule, evidence, review, approval, and completion
```

### 10.5 Initial Rail formation

Do not convert every idea into a task. Create only accepted current work:

```text
objective
bounded deliverable
owner or eligible role
dependencies
required evidence
review gate
approval gate
status
```

`[W] projects/<project>/...`  
`[W] projects/<project>/operations/ledger.json` when justified  
`[W] source and repository attachment manifests`

---

## 15. Node 11 — knowledge, skills, agents, models, and loops

### 11.0 Knowledge domains

> Which bodies of knowledge need durable curation rather than remaining ordinary project files?

Branches:

```text
small stable source set
  -> project sources only

manual corpus
  -> knowledge layer

corpus plus reusable ingestion/audit
  -> knowledge-system

externally changing corpus
  -> consider living-knowledge-system after maintenance contract
```

### 11.1 Skills

> Which procedures recur and need a verified playbook?

The system may discover skills, but must show provenance, trust status, tool use, credential access, mutation scope, and verification before adoption.

### 11.2 Agent topology

Start with one general or project-facing agent unless recurring roles justify specialists.

> Which responsibilities recur often enough that separate agents would improve ownership or review?

Candidate roles may include:

```text
concierge/project agent
researcher
architect/planner
implementer
documentation steward
reviewer
operations agent
specialized domain role
```

### 11.3 Agent binding questions

For each agent:

> Who owns and may stop this agent?

> Which organization and projects may it enter?

> Which sources may it read, and which files may it change?

> Which tools and skills may it use?

> May it communicate externally, spend, deploy, merge, or publish?

> Which actions require independent review or human approval?

> Which Rail items may it select?

> What evidence and handoff must it produce?

### 11.4 Runtime and model binding

> I found Claude Code, Codex, and Hermes. Which should operate this agent?

The system may recommend based on capability, privacy, cost, and current authentication, but user or organizational policy governs.

### 11.5 Loop gate

> Does this work need to recur automatically or continue across runs?

A loop is allowed only with:

```text
bounded objective
trigger or schedule
one Rail
selection rule
worker
independent verifier
evidence record
cost/spawn budget
human approval boundary
stop or kill condition
```

`[W] organization/knowledge/`  
`[W] organization/skills/`  
`[W] organization/agents/`  
`[W] model and runtime policies`  
`[W] loop contracts when justified`

---

## 16. Node 12 — Workframe outcome

### 12.0 Outcome selection

> How should you use the resulting system?

```text
1. Files and repositories only
2. Workframe on this machine for one user
3. Workframe on this machine for a trusted team
4. Attach to an existing Workframe
5. Plan a remote deployment
```

### 12.1 Repository-only

- generate runtime-neutral entry files;
- optionally generate adapters for authorized CLIs;
- no Workframe services;
- verify that a fresh runtime can enter the project.

### 12.2 Local single-user

- map user as authority root;
- configure local Workframe;
- attach files and projects;
- create runtime profiles;
- bind credentials through vault or use-in-place adapter;
- open verified workspace.

### 12.3 Trusted team

Additional questions:

> Who should have access?

> Which projects are shared?

> Are credentials user-funded, workspace-funded, or project-funded?

> Which roles may invite users, create agents, change permissions, or approve external actions?

### 12.4 Remote deployment

Stop and require a separate public-deployment plan covering HTTPS, auth, SMTP or equivalent, vault keys, backup, invite policy, supervisor isolation, brokered secrets, and threat-model verification.

---

## 17. Node 13 — plan, apply, verify, and enter

### 13.0 Plan summary

The system must show:

```text
Purpose and entity summary
Architectonic layers and justification
Files to create
Files to modify
Existing paths to adopt
Sources to mount/reference/copy/clone
Projects and Rail roots
Agents and runtime bindings
Permissions and prohibitions
Credential and funding paths
Workframe deployment mode
Commands to run
External data flows
Rollback/checkpoint plan
Remaining unknowns
```

### 13.1 Material review

> This plan would give the implementation agent write access to two repositories and permission to run local tests, but not to deploy or merge. Is that correct?

> Three source folders remain local-only. Their contents will not be sent to Claude. Is that correct?

### 13.2 Apply

```text
[D] validate grants
[D] validate paths and schemas
[D] create checkpoint
[D] install Architectonic closure
[D] write accepted local doctrine
[D] create attachments
[D] clone/adopt/mount approved sources
[D] create Rails
[D] install agent bindings
[D] deploy or attach Workframe
[D] record receipts
```

### 13.3 Verify

```text
[V] Architectonic manifest valid
[V] canonical read order resolves
[V] source provenance valid
[V] no excluded path attached
[V] one ledger per Rail-enabled project
[V] no duplicate work authority
[V] all agents have owner and stop authority
[V] runtime adapters invoke safely
[V] permissions deny out-of-scope access
[V] Workframe health and session binding pass
[V] new session loads correct startup context
```

### 13.4 Entry message

The first operational session should begin with a concise grounded context, not a generic greeting:

```text
You are entering <workspace>.
Human owner: <owner role>
Purpose: <accepted purpose>
Current project: <project>
Current objective: <objective>
Authority: <key grants and prohibitions>
Read first: <canonical files>
Rail: <single ledger root or none>
Known blocking unknowns: <list>
```

---

## 18. Node 14 — upkeep and resumption

### 14.0 Formation pause

> Setup is sufficiently grounded to operate, but these questions remain unresolved. Would you like to continue now, pause, or assign them to a project Rail?

### 14.1 Review triggers

Ask:

> When should this system ask you to review its understanding?

Candidates:

```text
when contradictory sources appear
when a governing source changes
before a new agent receives access
before external publication or spending
when a project becomes inactive
on a fixed review cadence
only when explicitly requested
```

### 14.2 Revoke and detach

Provide deterministic commands and clear consequences for:

- runtime authorization revocation;
- provider credential removal;
- source detachment;
- mount removal;
- deletion of copied snapshots;
- formation-state archive;
- Workframe profile disablement;
- agent stop;
- project archive.

### 14.3 Resume

A resumed session loads:

```text
accepted doctrine
active grants
relevant evidence
applied transactions
remaining contradictions
unanswered high-value questions
current project/Rail state
```

It must not restart the questionnaire or ask for information already established.

---

## 19. Question-generation contract

Before asking a generated question, the orchestrator must be able to fill:

```text
formation_stage:
evidence_ids:
known_claims:
unresolved_gap:
consequence_if_unresolved:
question:
answer_types:
write_target:
required_authority:
privacy_cost:
skip_condition:
```

A question is rejected when:

- it is answerable from accepted sources;
- it asks for unauthorized private information;
- it has no durable consequence or write target;
- it assumes the user's role or motive from access;
- it repeats a previously resolved question;
- it belongs to a later stage whose prerequisites are unresolved;
- it pressures consent;
- it converts a probabilistic inference into a factual premise;
- it exists only to complete a template.

## 20. Core conversational pattern

The canonical interaction pattern is:

```text
1. Here is what I found.
2. Here is what I think it may mean.
3. Here is what remains uncertain or contradictory.
4. Here is why that matters.
5. Here is the one question I need you to answer.
6. Here is what I propose to write or change.
7. Here is how you can correct, defer, or reject it.
```

That pattern is the operational meaning of “grill the user with documents.”
