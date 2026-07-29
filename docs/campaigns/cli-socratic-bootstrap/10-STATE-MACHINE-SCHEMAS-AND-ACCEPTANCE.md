# State Machine, Core Schemas, and Acceptance

## 1. Why a state machine is required

The formation process cannot rely on one chat transcript or one long model prompt. It must survive interruption, model switches, runtime failure, partial installation, user correction, and days between sessions.

The canonical formation state records what is accepted, proposed, authorized, applied, verified, revoked, and unresolved. It must not store raw private conversation by default.

## 2. Formation states

```text
NEW
  -> PRESENTATION_CONFIGURED
  -> PREFLIGHTED
  -> INFERENCE_PATH_SELECTED
  -> INFERENCE_AUTHORIZED | DETERMINISTIC_ONLY
  -> EVIDENCE_BOUNDARIES_SET
  -> INVENTORIED
  -> TELEOLOGY_GROUNDED
  -> ONTOLOGY_GROUNDED
  -> EPISTEMOLOGY_GROUNDED
  -> DOCTRINE_GROUNDED
  -> AUTHORITY_GROUNDED
  -> CONSTITUTION_GROUNDED
  -> PROJECTS_GROUNDED
  -> KNOWLEDGE_AGENTS_GROUNDED
  -> INSTALLATION_PLANNED
  -> PLAN_APPROVED
  -> APPLYING
  -> APPLIED
  -> VERIFYING
  -> OPERATIONAL
```

Auxiliary states:

```text
PAUSED
BLOCKED
NEEDS_REVIEW
PARTIALLY_APPLIED
ROLLING_BACK
ROLLED_BACK
REVOKED
ARCHIVED
FAILED_SAFE
```

A session may return to an earlier formation stage when new evidence invalidates an accepted conclusion. The transition must preserve the superseded decision and reason.

## 3. Transition rules

### 3.1 Discovery transitions

```text
NEW -> PRESENTATION_CONFIGURED
  requires supported renderer settings

PRESENTATION_CONFIGURED -> PREFLIGHTED
  requires completed read-only probe receipt
  prohibits model calls and mutations

PREFLIGHTED -> INFERENCE_PATH_SELECTED
  requires candidate list or explicit no-path result
```

### 3.2 Authorization transitions

```text
INFERENCE_PATH_SELECTED -> INFERENCE_AUTHORIZED
  requires active grant and optional verified adapter

INFERENCE_PATH_SELECTED -> DETERMINISTIC_ONLY
  requires explicit user choice or absence of usable path

any active state -> REVOKED
  when required grant is revoked and no permitted fallback is selected
```

### 3.3 Formation transitions

A stage advances when:

- its minimum durable concerns are accepted;
- material contradictions are resolved or explicitly preserved;
- required sources are authorized or declared unavailable;
- write targets are known;
- the next stage can proceed without pretending.

The stage does not require every possible question to be answered.

### 3.4 Mutation transitions

```text
INSTALLATION_PLANNED -> PLAN_APPROVED
  requires accepted exact plan and grants

PLAN_APPROVED -> APPLYING
  requires checkpoint and path revalidation

APPLYING -> APPLIED
  requires all mandatory operations applied or explicit partial state

APPLYING -> PARTIALLY_APPLIED
  requires receipt of completed and pending operations

APPLYING -> FAILED_SAFE
  requires no untracked state and recovery instructions
```

### 3.5 Verification transitions

```text
APPLIED -> VERIFYING
VERIFYING -> OPERATIONAL
  requires all mandatory gates pass

VERIFYING -> NEEDS_REVIEW
  when structure is valid but a material narrative/authority issue remains

VERIFYING -> ROLLING_BACK
  when applied state is unsafe or violates approved plan
```

## 4. Formation record

Illustrative shape:

```json
{
  "schema_version": "0.1.0",
  "formation_id": "frm_01JXYZ",
  "workspace_id": "northstar-practice-learning",
  "state": "PROJECTS_GROUNDED",
  "created_at": "2026-07-29T20:00:00-03:00",
  "updated_at": "2026-07-29T22:14:00-03:00",
  "presentation": {
    "mode": "guided",
    "language": "en",
    "large_print": false,
    "explanation_level": "normal"
  },
  "active_inference_adapter": "claude-cli",
  "active_grant_ids": ["grant_inference_claude", "grant_projects_metadata"],
  "stages": {
    "teleology": {"status": "accepted", "record_ids": ["decision_purpose_001"]},
    "ontology": {"status": "accepted", "record_ids": ["entity_org_001", "entity_project_001"]},
    "epistemology": {"status": "accepted_with_unknowns", "record_ids": ["policy_sources_001"]},
    "doctrine": {"status": "accepted", "record_ids": ["doctrine_001"]},
    "authority": {"status": "accepted", "record_ids": ["authority_001"]},
    "constitution": {"status": "accepted", "record_ids": ["constitution_001"]},
    "projects": {"status": "accepted", "record_ids": ["project_seminar"]}
  },
  "question_history": ["q_teleology_001", "q_ontology_004"],
  "unresolved_ids": ["unknown_seminar_ai_section"],
  "proposed_transaction_id": null,
  "last_checkpoint": "checkpoint_projects_grounded"
}
```

## 5. Grant record

```json
{
  "schema_version": "0.1.0",
  "id": "grant_projects_metadata",
  "subject": "formation:frm_01JXYZ",
  "capability": "filesystem.inventory",
  "scope": {
    "roots": ["/Users/mara/Projects"],
    "depth": 4,
    "include_hidden": false,
    "follow_links": false,
    "file_content": false
  },
  "purpose": "identify candidate active projects",
  "data_class": "metadata",
  "processing": "local",
  "issued_by": "user:mara",
  "issued_at": "2026-07-29T20:10:00-03:00",
  "expires_at": null,
  "revoked_at": null,
  "parent_grant": null
}
```

Grant matching must be exact or narrower. A child operation cannot broaden root, depth, data class, processing location, or mutation level.

## 6. Evidence item

```json
{
  "schema_version": "0.1.0",
  "id": "evidence_pitch_deck_001",
  "attachment_id": "attachment_strategy_docs",
  "source_uri": "file:///Users/mara/Documents/Strategy/pitch-deck.pdf",
  "display_path": "Strategy/pitch-deck.pdf",
  "content_hash": "sha256:...",
  "observed_at": "2026-07-29T20:22:00-03:00",
  "source_modified_at": "2026-06-12T11:41:00+02:00",
  "source_type": "presentation",
  "authority_status": "proposal_source",
  "sensitivity": "internal",
  "processing": {
    "local_read": true,
    "external_excerpt_ids": ["excerpt_001"]
  },
  "claims": ["claim_initial_customer_clinics"],
  "suspected_injection": false,
  "staleness": "review_required"
}
```

## 7. Claim record

```json
{
  "schema_version": "0.1.0",
  "id": "claim_initial_customer_clinics",
  "text": "The initial customer segment is independent clinics.",
  "classification": "decision",
  "status": "superseded",
  "scope": "business go-to-market",
  "source_ids": ["evidence_pitch_deck_001"],
  "inference": false,
  "accepted_by": "user:mara",
  "accepted_at": "2026-07-29T21:02:00-03:00",
  "superseded_by": "decision_initial_customer_professional_educators",
  "notes": "The deck describes an earlier direction."
}
```

Allowed classifications:

```text
fact
decision
assumption
inference
unknown
contradiction
stale_claim
superseded_decision
temporary_context
```

## 8. Question record

```json
{
  "schema_version": "0.1.0",
  "id": "q_teleology_001",
  "stage": "teleology",
  "evidence_ids": ["evidence_website_001", "evidence_plan_004"],
  "known_claim_ids": ["claim_consulting_001", "claim_software_001"],
  "unresolved_gap": "relationship between consulting and software purposes",
  "consequence": "determines whether one business line, transition, or funding relationship is modeled",
  "question": "Are consulting and software separate lines, a transition, or a funding relationship?",
  "answer_modes": ["natural_language", "choice"],
  "write_targets": ["organization/PURPOSE.md", "organization/DECISIONS.md"],
  "required_authority": "organization.owner",
  "privacy_cost": "low",
  "status": "answered",
  "answer_record_id": "answer_teleology_001"
}
```

## 9. Decision record

```json
{
  "schema_version": "0.1.0",
  "id": "decision_purpose_001",
  "title": "Consulting funds product development during transition",
  "scope": "organization",
  "decision": "Maintain consulting as a revenue line while product development becomes the long-term focus.",
  "reason": "Current revenue and explicit user direction",
  "source_ids": ["evidence_revenue_notes", "answer_teleology_001"],
  "owner": "user:owner",
  "status": "active",
  "decided_at": "2026-07-29T21:05:00-03:00",
  "review_trigger": "product revenue exceeds consulting revenue for three consecutive months"
}
```

## 10. Entity record

```json
{
  "schema_version": "0.1.0",
  "id": "entity_org_001",
  "type": "organization",
  "name": "Northstar Practice & Learning",
  "status": "active",
  "owner_ids": ["human_mara"],
  "parent_id": null,
  "relationships": [
    {"type": "contains_project", "target": "project_seminar"},
    {"type": "contains_project", "target": "project_website"}
  ],
  "source_ids": ["answer_ontology_001", "evidence_brand_001"],
  "unresolved": []
}
```

## 11. Source attachment

```json
{
  "schema_version": "0.1.0",
  "id": "attachment_seminar_materials",
  "mode": "mount_read_write",
  "source": "/Users/mara/Documents/Seminar 2026",
  "workspace_path": "mounted/seminar-materials",
  "project_ids": ["project_seminar"],
  "owner": "user:mara",
  "authority_status": "owner_confirmed",
  "sensitivity": "internal",
  "processing_policy": {
    "local_read": true,
    "external": "approved_excerpts_only"
  },
  "mutation_policy": {
    "allowed_roles": ["owner", "editor"],
    "forbidden_operations": ["delete_root", "change_permissions"]
  },
  "refresh": "live",
  "revocation": {
    "detach_supported": true,
    "delete_copies": false
  }
}
```

Allowed attachment modes:

```text
reference
adopt_existing_repository
clone_repository
mount_read_only
mount_read_write
copy_snapshot
import_extract
```

## 12. Project record

```json
{
  "schema_version": "0.1.0",
  "id": "project_seminar",
  "name": "September Seminar",
  "organization_id": "entity_org_001",
  "purpose_record_id": "purpose_seminar_001",
  "owner_ids": ["human_mara"],
  "root": "projects/september-seminar",
  "repository_ids": [],
  "attachment_ids": ["attachment_seminar_materials", "attachment_research"],
  "rail": {
    "enabled": true,
    "ledger_root": "projects/september-seminar/operations/ledger.json",
    "reason": "multi-session research, writing, review, and approval"
  },
  "status": "active",
  "known_unknown_ids": ["unknown_seminar_ai_section"]
}
```

## 13. Agent binding

```json
{
  "schema_version": "0.1.0",
  "id": "agent_web_maintainer",
  "archetype": "implementation-agent",
  "display_name": "Web Maintainer",
  "human_owner": "human_mara",
  "organization_scope": "entity_org_001",
  "project_scopes": ["project_website"],
  "runtime": {
    "adapter": "codex-cli",
    "profile": "northstar-web-maintainer",
    "auth_mode": "use_in_place"
  },
  "model_policy": {
    "provider": "runtime_account",
    "fallback": "deny_and_ask",
    "funding": "user_account"
  },
  "skills": ["skill_web_build", "skill_evidence_handoff"],
  "knowledge_attachments": ["knowledge_public_communications"],
  "grants": [
    "grant_repo_website_read_write",
    "grant_run_local_tests"
  ],
  "prohibitions": [
    "deploy_without_approval",
    "merge_without_approval",
    "read_other_projects",
    "change_credentials",
    "change_permissions"
  ],
  "rail": {
    "ledger_root": "projects/public-website/operations/ledger.json",
    "eligible_roles": ["web-maintainer"]
  },
  "review": {
    "required_for_completion": "reviewer",
    "human_approval_for": ["deployment", "publication"]
  },
  "stop_authority": ["human_mara", "self"]
}
```

## 14. Runtime adapter receipt

```json
{
  "schema_version": "0.1.0",
  "request_id": "req_01JABC",
  "formation_id": "frm_01JXYZ",
  "adapter": "claude-cli",
  "provider": "anthropic-account",
  "model": "runtime-selected",
  "purpose": "classify conflict between purpose sources",
  "evidence_ids": ["excerpt_website_001", "excerpt_plan_004"],
  "data_classes": ["internal_approved_excerpt"],
  "funding": "user_account",
  "started_at": "2026-07-29T20:45:00-03:00",
  "completed_at": "2026-07-29T20:45:08-03:00",
  "status": "success",
  "usage": null
}
```

## 15. Transaction plan

```json
{
  "schema_version": "0.1.0",
  "id": "txn_install_001",
  "formation_id": "frm_01JXYZ",
  "target_root": "/Users/mara/Northstar",
  "checkpoint": "checkpoint_pre_apply_001",
  "operations": [
    {
      "id": "op_001",
      "type": "create_file",
      "path": "organization/PURPOSE.md",
      "expected_existing": false,
      "content_source": "accepted_record:purpose_org_001"
    },
    {
      "id": "op_002",
      "type": "clone_repository",
      "source": "git@example.org:mara/public-site.git",
      "path": "repositories/public-website",
      "grant_id": "grant_clone_website"
    },
    {
      "id": "op_003",
      "type": "create_rail",
      "path": "projects/public-website/operations/ledger.json",
      "project_id": "project_website"
    },
    {
      "id": "op_004",
      "type": "attach_workframe_local",
      "deployment_mode": "local_single_user"
    }
  ],
  "status": "approved",
  "approved_by": "user:mara",
  "approved_at": "2026-07-29T22:30:00-03:00"
}
```

## 16. Transaction receipt

```json
{
  "transaction_id": "txn_install_001",
  "started_at": "2026-07-29T22:31:00-03:00",
  "completed_at": "2026-07-29T22:33:14-03:00",
  "status": "applied",
  "operations": [
    {"id": "op_001", "status": "verified", "result_hash": "sha256:..."},
    {"id": "op_002", "status": "verified", "commit": "abc123"},
    {"id": "op_003", "status": "verified", "rail_validation": "pass"},
    {"id": "op_004", "status": "verified", "health": "pass"}
  ],
  "rollback_available": true
}
```

## 17. Verification record

```json
{
  "schema_version": "0.1.0",
  "id": "verify_001",
  "workspace_id": "northstar-practice-learning",
  "status": "pass",
  "checks": [
    {"id": "architectonic_manifest", "status": "pass"},
    {"id": "canonical_read_order", "status": "pass"},
    {"id": "source_provenance", "status": "pass"},
    {"id": "private_exclusions", "status": "pass"},
    {"id": "rail_uniqueness", "status": "pass"},
    {"id": "agent_owner_stop", "status": "pass"},
    {"id": "runtime_scope", "status": "pass"},
    {"id": "workframe_health", "status": "pass"},
    {"id": "fresh_session_context", "status": "pass"}
  ],
  "remaining_unknowns": ["unknown_seminar_ai_section"],
  "verified_at": "2026-07-29T22:40:00-03:00"
}
```

## 18. Startup context contract

A runtime adapter renders a startup document from canonical records:

```json
{
  "actor_id": "agent_web_maintainer",
  "human_owner": "human_mara",
  "organization_id": "entity_org_001",
  "project_id": "project_website",
  "purpose_files": ["organization/PURPOSE.md", "projects/public-website/project_profile.md"],
  "authority_files": ["organization/CONSTITUTION.md", "organization/AUTHORITY.md"],
  "privacy_files": ["organization/PRIVACY.md"],
  "rail_root": "projects/public-website/operations/ledger.json",
  "permissions_summary": "project repository read/write; local tests; no deploy/merge/publish",
  "known_blockers": ["WEB-006 requires human publication approval"]
}
```

Runtime-specific files may render this contract into `AGENTS.md`, `CLAUDE.md`, Hermes profile files, or another adapter format. They may not weaken it or become a separate doctrine authority.

## 19. Completion gates

### Minimum operational grounding

- Purpose accepted.
- Relevant entity/project boundary accepted.
- Governing sources and knowledge classes defined.
- Human authority root identified.
- Privacy/exclusion scopes recorded.
- At least one useful project or knowledge outcome exists.
- Material contradictions are resolved or preserved.
- Architectonic plan validates.

### Project gate

- Purpose, scope, owner, sources, and success are explicit.
- Repository and attachment modes are explicit.
- Rail decision is explicit.
- If Rail exists, exactly one ledger root validates.

### Agent gate

- Human owner and stop authority exist.
- Runtime and auth mode are explicit.
- Organization/project scopes are explicit.
- Filesystem, tool, external-action, and spending grants are explicit.
- Review and approval gates are explicit.
- Rail selection contract is explicit when applicable.

### Workframe gate

- Deployment/attachment mode is explicit.
- User and role mappings validate.
- Vault/use-in-place credential path validates.
- Agent routes/profiles validate.
- Project file and Rail views resolve.
- Fresh session loads correct context.

## 20. Acceptance scenarios

### A-01 — Read-only status compatibility

Given a machine with Node, Git, Claude, and Codex, when `status --json` runs, then it reports normalized runtime status, performs no model call, reads no documents, and changes no files.

### A-02 — Ambiguous consent

Given the system asks to use Claude and the user answers with unrelated or ambiguous text, then no grant is created and the system asks for explicit intent without pressuring the user.

### A-03 — Use authenticated runtime in place

Given Claude Code is authenticated and the user authorizes it, then the system invokes the documented CLI interface without reading or copying private auth stores.

### A-04 — Local-only evidence

Given a folder is granted for local content processing but not external inference, then no excerpt from that folder appears in provider receipts or requests.

### A-05 — Excluded private zone

Given a clinical folder is excluded, then inventory, symlink traversal, attachments, copies, extracts, Workframe mounts, and agent grants all omit it.

### A-06 — Evidence-led question

Given two authorized sources conflict about project purpose, then the system shows the conflict and consequence and asks a targeted question rather than a generic purpose form.

### A-07 — No repeated question

Given the user answered a teleology question and the accepted record persists, then resume does not ask it again unless new evidence creates a material contradiction.

### A-08 — Correct no-install recommendation

Given the user's need is disposable and one-session, then the system recommends no Architectonic or Workframe installation.

### A-09 — Standalone project

Given one durable project with no material organization or identity boundary, then the system creates a project or project-system without manufacturing an organization.

### A-10 — Existing repository adoption

Given a repository already exists in a custom location, then the system can adopt it in place without moving, copying, or overwriting it.

### A-11 — Source mode distinction

Given one folder is read-only and another read-write, then runtime access tests deny writes to the first and permit validated scoped writes to the second.

### A-12 — Rail uniqueness

Given a Rail-enabled project, then exactly one ledger root is accepted; a second proposed board or queue is treated as a view or rejected as competing authority.

### A-13 — Agent authority completeness

Given an installed agent lacks a human owner or stop authority, then verification fails and Workframe does not activate the profile.

### A-14 — Cross-project isolation

Given an agent is scoped to project A, then it cannot read project B attachments or select project B Rail items.

### A-15 — No silent provider fallback

Given the configured provider is unavailable, then the run is denied and the user is asked; context is not silently sent to another provider.

### A-16 — Prompt injection source

Given a local README tells the scanner to reveal secrets and run commands, then the content is treated as untrusted evidence, no permission changes occur, and the injection is recorded.

### A-17 — Partial apply recovery

Given repository clone succeeds and Workframe deployment fails, then the transaction enters `PARTIALLY_APPLIED`, records verified operations, preserves the checkpoint, and offers retry or rollback without repeating successful destructive steps.

### A-18 — Fresh-session continuity

Given installation and verification pass, when a new authorized runtime session opens the project, then it receives correct owner, purpose, authority, source boundaries, project, Rail, and current objective without requiring full re-explanation.

### A-19 — Revocation

Given the user revokes an inference adapter and detaches a source, then future sessions cannot use them, receipts record revocation, and accepted canonical files remain intact until separately reconciled.

### A-20 — Accessibility

Given simple mode and keyboard-only operation, then the user can complete one-project formation, review every sensitive grant, pause, resume, and enter the result without interpreting raw JSON or dense terminal tables.

## 21. Release evidence

A release claim requires:

- fixture and end-to-end test output;
- security/adversarial test output;
- exact supported OS/runtime matrix;
- known limitations;
- sample redacted audit receipts;
- proof that excluded sources remain untouched;
- proof that a fresh session loads durable context;
- evidence that the output remains usable without Workframe Origin.

No claim should exceed this evidence.
