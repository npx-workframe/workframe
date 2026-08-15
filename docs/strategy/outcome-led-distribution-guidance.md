# Workframe outcome-led distribution guidance

**Status:** strategic guidance; subordinate to shipped behavior, `docs/public/`, the current strategy brief, and `docs/ledger/ledger.json`  
**Updated:** 2026-08-15  
**Source basis:** [Nevo David, “Postiz crossed $2M ARR while everybody says SaaS is dead”](https://x.com/wickedguro/status/2086788813301661865)  
**Scope:** interpretation for Workframe; the source author's channel claims are not adopted as universal facts

## Executive rule

Workframe should not be marketed as a list of agent infrastructure features. Its commercial meaning is:

> **Workframe turns scattered agent activity into governed, inspectable team output.**

The current technical definition remains important and accurate: Workframe is a self-hosted, multi-user workspace around Hermes Agent with authentication, rooms, files, credential isolation, activity records, and deployment tooling. That describes the product. It does not yet describe why a user should change behavior, install it, or pay for it.

The outcome ladder is:

```text
scattered people, agents, keys, chats, files, and tools
→ one private Workframe cell with explicit authority boundaries
→ assignments become runs, runs produce artifacts, and artifacts remain recoverable
→ the team can deliver agent-assisted work with less ambiguity, leakage, and operational drift
```

Workframe controls the workspace, authority model, records, and product behavior. It does not control model quality, user judgment, project demand, or whether an autonomous business becomes profitable. Marketing must preserve that boundary.

## What the source supports

The source argues that abundant software supply makes features easier to reproduce and distribution harder to earn. The durable lessons for Workframe are:

1. **Sell a user result, not a component inventory.** Auth, rooms, vaults, files, runs, and Docker Compose are mechanisms. A functioning private team cell and recoverable project output are the result.
2. **Authority must be demonstrated.** Install evidence, successful runs, artifacts, deployment verification, security boundaries, and real case studies are stronger than category language.
3. **Tutorials should solve the user’s job.** “How to run a private agent-assisted studio” is more useful than “we added another workspace feature.”
4. **Narrow category ownership is more achievable.** Workframe can become the obvious answer for a precise self-hosted team problem before competing for broad “AI workspace” or “autonomous business OS” territory.
5. **External sources matter for discovery.** GitHub, Hermes documentation, technical walkthroughs, independent evaluations, and real user references can make Workframe legible to search and answer engines.
6. **One canonical walkthrough can support many distribution assets.** A complete zero-to-artifact guide is more valuable than disconnected launch posts.
7. **Repeat what produces activation and retained use.** Views, stars, and installs are insufficient when users do not complete a governed run or return.

The source also recommends specific tactics such as X articles, lead magnets, UGC volume, and paid reposts. Those may be tested, but they are not core strategy for a developer infrastructure product.

## What Workframe should not import

Workframe should reject:

- the claim that conventional SEO is universally dead;
- generic founder content disconnected from installation, activation, or retained use;
- inflated “autonomous company” claims before the product and evidence support them;
- manufactured GitHub activity, fake testimonials, undisclosed promotion, or mass community posting;
- publishing install counts, user counts, security claims, time savings, or cost reductions without a recoverable measurement method;
- paying to amplify a funnel whose installation and activation path is not yet reliable;
- treating a successful scaffold or passing source test as evidence of a hardened public deployment;
- confusing model capability with Workframe capability.

## The result Workframe should sell

Workframe has three plausible near-term outcome packages. They share a product but address different users.

### 1. Private agent workspace for a small team

**Buyer:** a small software, creative, research, or operations team already using agents.  
**Problem:** work is fragmented across chat products, local CLIs, personal keys, repositories, and informal handoffs.  
**Intervention:** a controlled Workframe cell with team access, files, rooms, agent profiles, and deployment packaging.  
**Operational result:** the team has one place to coordinate agent-assisted work around durable files.  
**Proof:** successful install, authenticated users, completed run, produced artifact, and recoverable activity record.

### 2. Governed self-hosted agent execution

**Buyer:** an operator who wants self-hosted or controlled infrastructure.  
**Problem:** agents receive ambient access to credentials, files, and tools with weak accountability.  
**Intervention:** scoped profiles, credential leases, run gates, records, and deployment boundaries.  
**Operational result:** the operator can see who initiated work, what authority was granted, what it cost, and what it produced.  
**Proof:** complete run event chain, lease evidence, artifact links, approval behavior, and recovery verification.

### 3. Deployable agent-assisted project cell

**Buyer:** an agency, studio, lab, or technical operator repeatedly standing up project environments.  
**Problem:** every new project requires manually assembling UI, runtime, auth, files, deployment, and operating instructions.  
**Intervention:** `create-workframe` and a maintained reference deployment.  
**Operational result:** a project receives a repeatable cell rather than an improvised stack.  
**Proof:** scaffold success, environment validation, first login, first run, first artifact, and update or recovery evidence.

These are more credible wedges than “replace the company with agents.” The larger Social OS thesis can remain the north star while the near-term product sells a concrete operational improvement.

## Translate features into outcomes and evidence

| Product mechanism | User-facing result | Evidence required before a strong claim |
|---|---|---|
| `create-workframe` scaffolder | Start from a coherent project cell rather than assembling the stack manually | clean-machine install, exact version, successful boot, first login, first artifact |
| Multi-user auth and invites | Give a controlled team access to the same project environment | invite completion, role behavior, unauthorized-access tests |
| Files, Kanban, rooms, and chat | Keep durable work and handoffs outside ephemeral conversation | artifact creation, file history, task/run linkage, user observation |
| Credential vault and leases | Connect providers without pasting raw keys into agent chat | lease issuance, expiry, scope enforcement, secret-redaction tests |
| Runs, events, payer context, and receipts | Make agent work attributable and auditable | complete event chain, cost attribution, artifact references, failure records |
| Docker/VPS packaging | Reproduce a known deployment rather than inventing one per team | exact artifact, deployment proof, upgrade, backup, and recovery evidence |
| Hermes integration | Use Hermes inside a team and governance layer | supported-version matrix, profile execution, gateway and session evidence |

The result claim should never exceed the evidence column.

## Initial category territory

Workframe should avoid beginning with the broadest possible comparison set. “AI workspace,” “agent platform,” and “autonomous business OS” place the project against mature horizontal products and many loosely comparable tools.

More defensible query and category territory includes:

- self-hosted multi-user workspace for Hermes Agent;
- private agent workspace for a small team;
- Docker-packaged agent-assisted project environment;
- BYOK team workspace with credential isolation;
- auditable agent runs around shared project files;
- human-agent collaboration where files remain the source of truth.

The exact language must track shipped behavior. As Workframe adds runtime adapters beyond Hermes, broader terms may become supportable. Until then, Hermes is a valuable adoption surface even though it is not the long-term product boundary.

## Authority metrics

The source recommends publishing one authority metric. For Workframe, a single public number is useful only when it represents actual product value.

Candidate metrics, in order of maturity, are:

1. successful clean-machine installations by exact release;
2. percentage of installs reaching first authenticated login;
3. percentage reaching first successful agent run;
4. percentage producing a durable artifact;
5. time from install start to first governed artifact;
6. cells active again after 7 and 30 days;
7. teams that invite another human user;
8. runs with complete owner, payer, cost, authority, and artifact records;
9. upgrade, backup, and recovery success by release;
10. paid hosted, support, or managed-deployment customers when received payment can be verified.

Do not publish any of these until instrumentation, privacy treatment, denominator, period, and failure definition are explicit.

GitHub stars, package downloads, followers, and launch impressions can show awareness. They do not prove that Workframe produces a useful cell.

## The canonical activation story

Workframe needs one maintained, end-to-end source of truth:

> **From zero to the first governed project artifact.**

That walkthrough should show, using one exact supported release:

1. prerequisites and trust assumptions;
2. installation or scaffold;
3. first authenticated operator;
4. provider connection without exposing a raw key to chat;
5. one project file and one bounded assignment;
6. one agent run;
7. resulting file, commit, document, or other artifact;
8. recorded initiator, runtime, cost, authority, and outcome;
9. failure handling and where truth is stored;
10. update, backup, or teardown path.

This is simultaneously onboarding, product proof, documentation, a demo script, a case-study template, an answer-engine source, and a conversion asset.

Short videos, posts, talks, and launch pages should derive from this canonical flow rather than inventing different product stories.

## Tutorials should solve operational problems

High-value Workframe tutorials include:

- how to give a small team one private Hermes workspace;
- how to keep provider keys out of prompts and agent-visible files;
- how to bind an agent run to an owner, budget, and artifact;
- how to structure files, boards, and chat so project truth survives the session;
- how to deploy an invite-only Workframe cell on a controlled VPS;
- how to audit what an agent changed and what it cost;
- how to recover a cell after an interrupted upgrade;
- how to decide when Hermes alone is sufficient and when Workframe is useful.

Each tutorial should name the tested version, environment, mode, limitations, and source files. The goal is not content volume. It is to make the user’s decision and first successful outcome easier.

## Distribution surfaces

### GitHub and the Hermes ecosystem

These are Workframe’s strongest near-term surfaces because the product is technical, inspectable, and currently Hermes-centered.

Use them for:

- code and release proof;
- exact install guides;
- issues and real user questions;
- comparison and integration documentation;
- reference cells and examples;
- independent audits and reproducible findings.

### Search and answer engines

Conventional search remains useful for high-intent questions such as installation, self-hosting, Hermes team use, credential isolation, and deployment. Answer-engine visibility should be earned through consistent documentation and external corroboration, not `llms.txt` or schema alone.

### X, LinkedIn, video, and talks

Use these to distribute demonstrations, architectural lessons, security decisions, and user outcomes. A short demonstration should lead back to a canonical guide, release, or case study.

### Product launches and paid amplification

Use only when the release can reliably move a new user from discovery to first value. A launch that produces traffic but exposes a broken installation or unclear product boundary is negative proof.

## Funnel and activation model

The Workframe funnel should be measured as:

```text
discovery
→ qualified documentation or landing visit
→ install or hosted-cell request
→ environment boots
→ first authenticated login
→ provider connected
→ first bounded run
→ first durable artifact
→ second session or invited teammate
→ retained use
→ paid hosted, support, deployment, template, or marketplace action
```

The activation event is not merely `npm install` or a repository clone. The strongest candidate is **the first governed artifact produced by a recorded run**. This should be validated with users before it becomes canonical.

## Monetization should package outcomes

Potential paid packages should be described by what the buyer receives:

- a managed private Workframe cell with verified deployment and recovery;
- a dedicated team environment with support and updates;
- a deployment review and hardening engagement;
- a reusable studio or project template that reaches a defined first outcome;
- hosted credits and execution with transparent ownership and cost attribution;
- marketplace assets that improve a specific workflow.

Selling undifferentiated hosting, tokens, or “AI agents” alone recreates the commodity problem described by the source.

## Immediate operating guidance

1. Choose one initial buyer and one first governed artifact they care about.
2. Verify the complete installation-to-artifact path on a clean environment.
3. Instrument the funnel without collecting unnecessary private project content.
4. Publish one canonical zero-to-artifact walkthrough tied to an exact release.
5. Derive tutorials and demonstrations from real setup and operating questions.
6. Collect case studies that state environment, version, user, task, result, limitation, and evidence.
7. Build category association around the narrowest accurate terms first.
8. Repeat the channel and message that produce activated, retained cells rather than the most impressions.
9. Delay paid amplification until activation and recovery are dependable.
10. Feed every repeated failure back into product, documentation, and release gates.

## Final decision rule

A distribution activity is valuable when it increases at least one of:

```text
qualified installs
successful activation
credible product proof
retained cells
paid deployment or support
```

The lesson is not that Workframe needs louder marketing. It needs a shorter and better-evidenced chain from **problem → cell → governed run → durable artifact → retained operational value**.
