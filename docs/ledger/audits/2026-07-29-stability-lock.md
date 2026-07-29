# Workframe Stability Lock Audit

**Date:** 2026-07-29  
**Scope:** Workframe product and standalone CLI  
**Posture:** adversarial architecture, blue-team hardening, red-team tenant boundary review, recovery and release wargame  
**Authority:** `docs/ledger/ledger.json` remains the canonical work ledger

## Executive verdict

Workframe is no longer an architectural prototype. The repository contains substantial multiplayer product behavior, runtime provisioning, credential brokerage, rooms, messages, files, activity, invites, provider connections, install/update tooling, and public deployment checks.

The current goal is not to add more collaboration concepts. It is to prove that the implemented system is tenant-safe, repeatably installable, recoverable, and stable across the four target cells.

The product must not invite the real social pilot until the target-workspace authorization finding is closed.

## North star

A multiplayer social AI workspace where humans bring repositories, projects, and agents into shared business cells, delegate work, communicate, share files, and supervise delivery while runtimes and models remain replaceable.

## Current weekly outcome

1. Close or actively remediate `WF-045` target-workspace authorization.
2. Freeze one immutable source/package/configuration baseline.
3. Prove that same artifact across:
   - `demo.workfra.me`;
   - `abx.alanborger.com`;
   - `team.click.blue`;
   - `dev.glitchtrader.com`.
4. Reconcile the closed/unmerged CLI candidate and complete `WF-CLI-001` only.

## SWOT

### Strengths

- Real multiplayer entities and flows exist: workspaces, memberships, invites, rooms, DMs, Spaces, messages, mentions, reactions, files, memory, budgets, grants, activity, and SSE.
- Invite acceptance binds the authenticated user's email to the invited address and provisions per-user agent runtimes.
- Run authority and payer resolution are explicit rather than ambient.
- Opaque broker leases keep provider secrets out of Hermes profiles and support revocation.
- Route registration centralizes method/path/auth level and has source-shape audits.
- Public deployment preflight checks secure mode, HTTPS, required secrets, Docker socket isolation, broker posture, and anonymous data denial.
- The ABX deployment demonstrates real human-to-agent and agent-to-workspace-tool behavior.
- The CLI campaign is already decomposed into dependency-ordered slices rather than one giant installer.

### Weaknesses

- Request-level role derives from the user's highest role across all workspaces, not the target workspace.
- Resource-scope authorization is distributed across handlers and inconsistent.
- Some session-authenticated routes resolve a caller-supplied workspace/resource without one uniform tenant gate.
- The route registry proves that a route has an auth class; it does not prove the caller may access the target resource.
- Final product-ledger items still describe older package baselines and themes rather than the current stability campaign.
- GitHub OAuth is real, but the product contract for clone/status/pull/commit/push authority and receipts is not yet explicit.
- Recovery, backup/restore, and repeated installation evidence are weaker than feature breadth.
- The standalone CLI's previous candidate is closed and unmerged, but the ledger contains multiple historical candidate references.

### Opportunities

- A secure four-cell baseline can become the first credible public proof of repeatable human-agent collaboration.
- One stable installer and acceptance matrix can turn Workframe from a personal system into a product collaborators can test.
- A narrow Socratic CLI can become the entry point without taking ownership of existing runtimes or projects.
- A versioned noninteractive Architectonic plan/apply contract can prevent duplicated composition logic.
- The existing doctor and preflight tooling can become a machine-readable release gate rather than ad hoc troubleshooting.

### Threats

- Cross-workspace data or authority leakage would invalidate the social product premise.
- Four manually repaired deployments would create four forks and false confidence.
- Continuing feature work before a regression lock would repeat the cycle in which small fixes create larger regressions.
- Ambient terminal/Git authority could bypass Workframe's intended collaboration and receipt model.
- Long-lived runtime credential leases make revocation correctness critical.
- Treating `trusted_team` assumptions as `public_multi_user` safety could expose sensitive workspace data.
- A conversational CLI that installs or adopts too early could damage existing user environments.

## P0 findings

### WF-045 — target-workspace authorization

Issue: https://github.com/npx-workframe/workframe/issues/14

#### Source basis

- `services/workframe-api/auth_gate.py::workspace_role_for_user` selects the highest active role across every workspace.
- `apply_session_user` stores that global role on the request.
- `handler_is_active_workspace_member` accepts a global owner/admin before resolving target membership.
- `services/workframe-api/route_registry.py` marks many workspace/resource paths as session-authenticated but has no resource-scope resolver in the route contract.
- Handler modules contain a mixture of correct local membership checks and direct resource access.

#### Required fix shape

Do not add more local `if` statements route by route. Create one deny-by-default resource-scope authorization seam that resolves target workspace from:

- workspace path ID/slug;
- room ID;
- memory ID;
- agent profile ID;
- invite token;
- any future workspace-owned resource.

The authorization contract must distinguish:

- stack operator;
- target-workspace owner/admin/member;
- invited-but-not-yet-member identity;
- public/install-window exception;
- single-user-local exception.

#### Adversarial matrix

Use at least:

1. owner of workspace A only;
2. admin of A and member of B;
3. member of B only;
4. invited identity for B;
5. unrelated authenticated user;
6. anonymous caller.

For every scoped GET/POST/PATCH/DELETE and SSE setup, assert both response and unchanged database/filesystem state.

#### Edge cases

- owner of A requests B by UUID versus slug;
- room ID from B under a request whose current workspace is A;
- deleted/suspended membership;
- deleted workspace with surviving resource row;
- stale session after role downgrade;
- invite accepted while another active membership exists;
- token enumeration and consistent 403/404 behavior;
- agent profile shared by template slug but owned by another workspace;
- file path that is safe but belongs to the wrong workspace root;
- SSE connection authorized before membership is revoked;
- role changed while a long-running stream or agent turn is active;
- service token versus human session authority;
- `DEV_LOCAL_UNSAFE` accidentally enabled in a public deployment.

#### Stop line

No real social-pilot invitations and no public-multi-user stability claim until the matrix passes independently.

### WF-046 — immutable four-instance baseline

Issue: https://github.com/npx-workframe/workframe/issues/15

#### Required baseline identity

Record:

- source commit;
- package versions;
- packed artifact hashes;
- compose and configuration schema;
- migration revision;
- UI build identity;
- runtime/Hermes version;
- enabled deployment mode;
- rollback artifact.

#### Required matrix

- install/update from exact artifact;
- owner and invited-member login;
- user-user and user-agent DM;
- Space mention and response;
- file create/read/update and protected-path denial;
- provider connection without secret disclosure;
- agreed disposable repository journey;
- restart and continuity;
- backup and restore;
- target-workspace denial;
- doctor and public preflight.

#### Edge cases

- update from the previous two published versions;
- interrupted migration or container restart during update;
- stale browser assets after API migration;
- changed domain/HTTPS host after initial install;
- restored database with different install ID or vault key;
- missing runtime profile on member reacceptance;
- package rollback after a forward-only schema migration;
- concurrent invites or duplicate invite acceptance;
- SMTP unavailable after membership commit;
- one instance with GitHub OAuth configured and another without;
- disk-full or permission-denied workspace volume;
- copied deployment accidentally sharing secrets or install identity.

### WF-CLI-001 — smallest trustworthy Socratic seed

Issue: https://github.com/npx-workframe/workframe/issues/16

The previous candidate is closed and unmerged. Reconcile current main and useful candidate commits before implementation.

The slice ends at:

- read-only discovery;
- exact inference/billing path;
- explicit cancellable verification;
- preferred name and one objective;
- memory-only mirror.

It does not install, adopt, write, deploy, store credentials, call Docker/SSH, create jobs, or start `WF-CLI-002`.

#### Edge cases

- installed binary but unauthenticated account;
- account and API key both present;
- two keys for the same provider;
- question or hedge interpreted as a choice;
- negative and positive consent in one sentence;
- Ctrl+C during HTTP body read or child process;
- child ignores graceful termination;
- EOF at every prompt;
- verification succeeds but output is malformed;
- credential appears in child stderr;
- Windows npm shim versus POSIX symlink;
- provider timeout after the user cancels;
- model returns an interpretation that changes the user's stated objective.

## P1 findings

### Git journey ownership

Decide and document whether repository operations are:

1. a Workframe product primitive with scoped operation receipts;
2. a bounded agent tool capability using user credentials;
3. outside the current baseline.

Questions:

- Which user pays and whose credential is used?
- Which filesystem root may be mutated?
- How are branch, remote, push, conflict, and destructive operations approved?
- Does an agent have ambient terminal access beyond the selected repository?
- What durable receipt proves who initiated and who executed the operation?
- Can a workspace owner grant another member use of a repository credential without exposing it?

### Credential lease lifecycle

Verify revocation on:

- membership removal;
- role downgrade;
- provider disconnect;
- credential replacement;
- workspace deletion;
- agent deletion;
- payer/funding-mode change;
- runtime profile purge;
- restore from backup;
- expiration during a long-running turn.

### Backup/restore contract

Define one atomic-enough recovery unit for:

- `workframe.db`;
- credential vault metadata and required key material;
- Files workspace;
- runtime profiles and overlays;
- install/config manifest;
- migration revision.

Restoring a database without its corresponding vault/config/profile state must fail visibly rather than partially operate.

### Long-running streams and revocation

SSE and agent turns should re-evaluate or respond to revocation. A caller authorized at connection start must not retain indefinite access after membership or role removal.

## P2 findings

- Continue decomposition only when it removes an active ownership ambiguity or supports a P0 regression.
- Do not reopen broad UI/theme campaigns before the baseline is locked.
- Do not add new product primitives until core collaboration and recovery pass.
- Performance tuning should follow measurements from the four-cell matrix.

## P3 / deferred

- broad marketplace/economic features;
- public cloud multi-tenancy beyond the current deployment contract;
- additional runtimes beyond the accepted adapter boundary;
- mobile/electron expansion;
- generalized terminal product.

## White-hat threat model

### Assets

- workspace files and project source;
- messages and memory;
- user/provider credentials;
- runtime profiles and agent identity;
- repository authority;
- billing/payer state;
- audit and run receipts;
- deployment configuration and vault keys.

### Attack surfaces

- public/install/auth routes;
- session and role attachment;
- workspace/resource IDs;
- file path handling;
- invite tokens and email flows;
- OAuth callbacks and pending state;
- internal LLM/action proxies;
- long-lived runtime leases;
- supervisor and Docker/process control;
- uploaded files and content rendering;
- SSE streams;
- agent terminal and Git tools;
- backup/restore and cloned deployments.

### Abuse cases to test

- horizontal tenant access;
- vertical role escalation;
- service-token confusion with human identity;
- confused-deputy provider billing;
- credential use after membership removal;
- invite token reuse or identity mismatch;
- path traversal/symlink escape;
- stored content injection into UI/agent context;
- agent prompt content requesting secret/file exfiltration;
- hidden endpoint discovered outside route registry;
- installation window reopened after setup;
- downgrade/restore reintroducing unsafe configuration;
- cross-instance shared OAuth or vault identity;
- resource exhaustion through streams, uploads, model calls, or runtime spawning.

## Blue-team controls

- target-resource authorization metadata in the route registry;
- generated route/scope coverage audit;
- two-workspace fixtures in CI;
- short-lived or explicitly revocable capability grants;
- append-only audit for grants, credentials, Git operations, role changes, and restore;
- secure defaults with no public fallback;
- exact artifact hashes and migration gates;
- backup/restore drill;
- per-cell secrets and install identities;
- core regression suite required by release manifest.

## Wargames

### Wargame 1 — malicious member

A member of workspace A learns a room ID, agent ID, memory ID, and invite token from B. Attempt every registered method and stream. Success requires zero data disclosure and zero state mutation.

### Wargame 2 — compromised agent

An agent is prompted to read another workspace, reveal provider keys, clone an unrelated repository, or push to an unapproved remote. Success requires denied authority with an audit record and no secret in context/logs.

### Wargame 3 — interrupted update

Kill containers/processes during migration, runtime provisioning, and UI/API rollout. Success requires deterministic recovery or rollback without mixed schema/build identity.

### Wargame 4 — credential revocation mid-turn

Remove a member/provider credential while a turn is active. Success requires bounded completion or interruption according to policy and denial of subsequent broker calls.

### Wargame 5 — restore to a new host

Restore backup under a new domain/host and different machine. Success requires explicit rebind of host/OAuth/HTTPS/config identity and no accidental reuse of another cell's secrets.

## Ledger reconciliation

The implementation PRs should update the canonical ledger as follows:

- add `WF-045` P0 before external pilot work;
- add `WF-046` P0 depending on `WF-045`;
- reconcile stale UI/install evidence against the current release instead of keeping multiple final-baseline items active;
- keep `WF-CLI-001` as the only executable CLI item and correct closed PR/head evidence;
- leave `WF-CLI-002+` dependency-gated;
- defer unrelated UI and feature work until the baseline passes.

GitHub issues are implementation mirrors, not a replacement ledger.

## Recommended execution order

1. `WF-045` design/spec and route-scope matrix.
2. Implement target-resource authorization in bounded route groups with generated coverage.
3. Independent security review.
4. Freeze the exact `WF-046` artifact.
5. Run the same matrix on all four cells and record recovery/rollback.
6. Separately reconcile and finish `WF-CLI-001`.
7. Lock the baseline and require its regression set for later changes.

## Questions for the operator

These questions do not block source-level security work, but they must be answered before final acceptance:

1. Is the near-term supported deployment mode `trusted_team`, `public_multi_user`, or both?
2. Are the four cells intentionally separate security/secret/database boundaries?
3. Which repository operation is required for the first social pilot: clone only, pull/push, or full commit workflow?
4. Which users may bring provider/repository credentials, and may a workspace pay for others?
5. What data and runtime state must survive backup/restore versus be reprovisioned?
6. What is the permitted terminal authority in the first pilot?
7. Which exact Workframe release should become the lock candidate after `WF-045`?
8. Is `team.click.blue` required this week or may the first baseline use ABX and demo before the other two cells?

## Stop line

No claim of stable multiplayer operation, no real social-pilot invitation, and no new foundational feature until the P0 tenant boundary and immutable baseline acceptance are closed with exact evidence.