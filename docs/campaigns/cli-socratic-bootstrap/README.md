# Workframe Origin — CLI Socratic Bootstrap Campaign

> **Status:** construction campaign, documentation only  
> **Branch:** `campaign/cli-socratic-bootstrap`  
> **Product surface:** CLI-first bootstrap and formation flow  
> **Working product name:** **Workframe Origin**  
> **Tagline:** **Your work should outlive the chat.**

## Campaign purpose

This campaign defines a separate, CLI-focused construction effort for a consent-driven system that discovers a user's computing environment, identifies available agentic runtimes and model access, conducts an evidence-led Socratic formation process, installs a customized Architectonic system of record, and attaches that system to a Workframe execution surface and one or more agentic runtimes.

It addresses a common failure in present-day AI use: a person spends an hour explaining who they are, what they are building, what matters, what already exists, and what constraints apply; the session ends; the next agent begins without that understanding. The problem is not merely conversational memory. The missing layer is a durable, user-owned account of purpose, entities, knowledge, authority, projects, decisions, unknowns, permissions, and current work.

Workframe Origin turns a first-run setup into an epistemic bootstrap process. It actively tries to answer, with the user and from authorized evidence:

```text
Who am I?
Who is my user?
What are we trying to accomplish?
What already exists?
What is known?
What is assumed?
What is unknown or contradictory?
What may I access, change, publish, spend, or execute?
How can I be useful now?
How will this understanding survive the current session and model?
```

## Isolation boundary

This directory describes a new construction campaign. It does **not** claim to describe the current Workframe product, the current `create-workframe` installer, or the current contents of the Architectonic packages as shipped behavior.

The campaign:

- learns from current Workframe principles and architecture;
- learns from the Architectonic package family and its adaptive layers;
- uses ABKB as a reference for a mature, instantiated operating-memory system;
- does not copy ABKB's private content or assume its layout is universally correct;
- does not modify current Workframe product code in this documentation pass;
- does not modify Architectonic repositories;
- does not silently merge this proposal into the existing product roadmap;
- requires an explicit later decision before implementation is integrated into canonical Workframe surfaces.

## Product thesis

The canonical chat transcript should remain disposable. Durable understanding should be explicit, inspectable, correctable, source-grounded, portable across runtimes, and owned by the user.

```text
conversation
  -> evidence-led questions
  -> explicit decisions and preserved unknowns
  -> Architectonic files and contracts
  -> Workframe users, rooms, runs, approvals, and artifacts
  -> runtime-specific sessions that can resume from the same ground truth
```

Architectonic provides the durable organizational and knowledge contract. Workframe provides the operating environment in which humans and agents use that contract. Existing runtimes remain replaceable execution engines.

## Source principles retained by this campaign

1. **Files outrank chat.** Durable project and organizational truth belongs in inspectable files, not only in a session transcript.
2. **Access is not authority.** Discovering a folder, repository, credential, runtime, or account does not authorize use, mutation, disclosure, spending, or external effects.
3. **Evidence precedes inference.** Project and identity knowledge comes from recoverable sources or explicit user confirmation.
4. **Unknowns remain unknown.** The system must label assumptions, contradictions, stale claims, and open questions rather than filling templates with plausible fiction.
5. **Start with the smallest justified structure.** A project may stand alone. An organization, knowledge system, agent team, Rail, or living-knowledge process is added only when the durable concern requires it.
6. **One live work authority per project.** When work must survive sessions, roles, dependencies, review, or approval, the project binds one Rail ledger.
7. **Installed agents have no inherent authority.** Runtime permissions, budgets, tools, data access, review gates, and stopping rights must be explicitly bound.
8. **Discovery is progressive and revocable.** The system asks separately for machine metadata, path inventory, file metadata, content access, external transmission, and mutation rights.
9. **Deterministic controls surround probabilistic interpretation.** Models may interpret, compare, question, and draft; deterministic code owns permission checks, schemas, writes, credentials, installation, rollback, and verification.
10. **The user can leave.** The resulting Markdown, manifests, repositories, and ledgers remain usable without Workframe Origin or a particular model provider.

## Intended command surface

The user-facing package remains conceptually simple:

```bash
npx workframe
```

Possible subcommands for the campaign:

```bash
npx workframe status       # read-only environment and runtime discovery
npx workframe start        # begin a new formation session
npx workframe resume       # resume a persisted formation session
npx workframe inspect      # inspect authorized evidence and source attachments
npx workframe plan         # show the proposed Architectonic and Workframe installation
npx workframe apply        # execute approved writes and installation transactions
npx workframe verify       # validate doctrine, attachments, rails, agents, and runtime bindings
npx workframe revoke       # revoke grants, detach sources, or disable runtime access
```

The final command names are product decisions. The invariant is that discovery, authorization, interpretation, planning, mutation, and verification remain distinct states.

## Document index

| File | Purpose |
|---|---|
| [`01-POSITIONING.md`](./01-POSITIONING.md) | Name, tagline, one-sentence description, one-paragraph description, audiences, and product promise. |
| [`02-ONE-PAGER.md`](./02-ONE-PAGER.md) | Five-paragraph executive summary of the problem, product, process, and outcome. |
| [`03-PRD.md`](./03-PRD.md) | Product requirements, personas, user journey, capabilities, constraints, metrics, and non-goals. |
| [`04-ARCHITECTURE.md`](./04-ARCHITECTURE.md) | Components, trust boundaries, data flow, runtime adapters, file layout, deployment modes, and transaction model. |
| [`05-PHILOSOPHICAL-AND-REASONING-MODEL.md`](./05-PHILOSOPHICAL-AND-REASONING-MODEL.md) | Formation order from teleology onward, knowledge classes, and deterministic/probabilistic responsibility. |
| [`06-SOCRATIC-SCRIPT.md`](./06-SOCRATIC-SCRIPT.md) | Full adaptive setup script in tree form, including evidence-led branches and write targets. |
| [`07-INSTALLED-OUTCOME-EXAMPLE.md`](./07-INSTALLED-OUTCOME-EXAMPLE.md) | A fully instantiated example with organization, constitution, team, projects, Rails, knowledge, files, repositories, permissions, Workframe, and multiple runtimes. |
| [`08-SECURITY-PRIVACY-AUTHORITY.md`](./08-SECURITY-PRIVACY-AUTHORITY.md) | Consent, local scanning, secret handling, external inference, audit, revocation, and threat model. |
| [`09-IMPLEMENTATION-CAMPAIGN.md`](./09-IMPLEMENTATION-CAMPAIGN.md) | Isolated implementation phases, workstreams, deliverables, gates, and integration rules. |
| [`10-STATE-MACHINE-SCHEMAS-AND-ACCEPTANCE.md`](./10-STATE-MACHINE-SCHEMAS-AND-ACCEPTANCE.md) | Resumable state machine, core records, transaction boundaries, completion gates, and acceptance scenarios. |
| [`11-SOURCE-GROUNDING.md`](./11-SOURCE-GROUNDING.md) | Repositories and source documents reviewed, retained principles, source conflicts, and transcript decisions. |

## Definition of success

A successful campaign produces a system that can be installed by a non-specialist, understand only what the user has authorized it to inspect, conduct a meaningful Socratic dialogue rather than a static questionnaire, persist the result as a customized Architectonic system, organize existing projects and repositories without destroying their boundaries, attach each durable project to one Rail when needed, bind agents to explicit permissions and runtime adapters, and open a Workframe workspace where a future session can continue without requiring the user to explain the entire world again.
