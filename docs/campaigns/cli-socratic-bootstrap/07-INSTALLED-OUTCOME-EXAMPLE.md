# Fully Installed Outcome Example

## 1. Scenario

This example shows the intended end state after a complete Workframe Origin formation session. It is fictional and demonstrates structure, not a universal template.

**User:** Mara, a psychiatrist in Paris who is beginning to use AI cautiously.  
**Existing machine:** MacBook Air with Claude Code authenticated, Git installed, no Docker engine running, several document folders, one existing website repository, and a collection of seminar materials.  
**Initial request:** organize her professional work, create a safe AI-assisted education project, and stop re-explaining the same context in each Claude session.  
**Critical boundary:** no patient-identifiable information may be inspected, copied, indexed, or transmitted to AI.

During formation, Workframe Origin discovers that Mara's “work” is not one project. It consists of a professional practice, a separate education initiative, a public website, and a personal research corpus. The system proposes an organization only because governance, privacy, shared branding, multiple projects, and several recurring agent roles materially interact.

## 2. Accepted teleology

```text
Northstar Practice & Learning exists to improve the quality and reach of
Mara's non-clinical professional work through carefully bounded education,
research, communication, and administrative systems.

The system must reduce repeated explanation and administrative overhead
without allowing patient-identifiable information into AI-accessible scopes.

Initial success means:
- the September seminar can be developed from grounded sources;
- the public website can be maintained coherently;
- future agents can resume both projects from durable context;
- private clinical data remains outside the workspace;
- Mara can inspect, correct, and revoke every integration.
```

## 3. Installed workspace tree

```text
~/Northstar/
├─ START_HERE.md
├─ architectonic.json
├─ organization/
│  ├─ PURPOSE.md
│  ├─ DOCTRINE.md
│  ├─ CONSTITUTION.md
│  ├─ IDENTITY.md
│  ├─ AUTHORITY.md
│  ├─ PRIVACY.md
│  ├─ DECISIONS.md
│  ├─ KNOWN_UNKNOWNS.md
│  ├─ people/
│  │  └─ owner.md
│  ├─ teams/
│  │  └─ core-team.md
│  ├─ knowledge/
│  │  ├─ README.md
│  │  ├─ ontology/
│  │  │  ├─ concepts.md
│  │  │  └─ relationships.md
│  │  ├─ professional-education/
│  │  ├─ public-communications/
│  │  └─ research-method/
│  ├─ skills/
│  │  ├─ source-review/
│  │  ├─ seminar-outline/
│  │  ├─ website-content-review/
│  │  └─ evidence-backed-handoff/
│  ├─ agents/
│  │  ├─ concierge/
│  │  │  ├─ agent.json
│  │  │  ├─ PURPOSE.md
│  │  │  ├─ PERMISSIONS.md
│  │  │  ├─ skills.json
│  │  │  └─ knowledge.json
│  │  ├─ research/
│  │  ├─ editor/
│  │  ├─ web-maintainer/
│  │  └─ reviewer/
│  └─ operations/
│     ├─ agent-registry.json
│     ├─ permission-matrix.json
│     ├─ model-policy.json
│     └─ review-policy.md
├─ projects/
│  ├─ september-seminar/
│  │  ├─ START_HERE.md
│  │  ├─ project_profile.md
│  │  ├─ PURPOSE.md
│  │  ├─ SCOPE.md
│  │  ├─ SOURCES.md
│  │  ├─ DECISIONS.md
│  │  ├─ ASSUMPTIONS.md
│  │  ├─ OPEN_QUESTIONS.md
│  │  ├─ RISKS.md
│  │  ├─ repositories.json
│  │  ├─ attachments.json
│  │  └─ operations/
│  │     └─ ledger.json
│  ├─ public-website/
│  │  ├─ START_HERE.md
│  │  ├─ project_profile.md
│  │  ├─ architecture.md
│  │  ├─ content-doctrine.md
│  │  ├─ repositories.json
│  │  ├─ attachments.json
│  │  └─ operations/
│  │     └─ ledger.json
│  └─ research-library/
│     ├─ START_HERE.md
│     ├─ project_profile.md
│     ├─ knowledge-policy.md
│     ├─ source-registry.json
│     └─ operations/
│        └─ ledger.json
├─ repositories/
│  └─ public-website/                 # cloned Git repository
├─ mounted/
│  ├─ seminar-materials/              # read-write mount to existing folder
│  └─ professional-research/          # read-only mount to existing folder
├─ snapshots/
│  └─ previous-seminar-2025/          # copied dated snapshot with provenance
├─ sources/
│  ├─ attachments.json
│  ├─ provenance/
│  │  ├─ seminar-materials.json
│  │  ├─ professional-research.json
│  │  ├─ website-repository.json
│  │  └─ previous-seminar-2025.json
│  └─ extracts/
│     └─ approved-public-biography.md
├─ .architectonic/
│  ├─ installed/
│  ├─ derived/
│  └─ verification/
├─ .workframe-origin/
│  ├─ formation.json
│  ├─ grants.json
│  ├─ evidence.json
│  ├─ audit/
│  ├─ checkpoints/
│  └─ transactions/
└─ Workframe/
   ├─ Agents/
   ├─ Files/                           # workspace view over approved roots
   ├─ data/
   └─ deployment manifest
```

The clinical-record folders do not appear in this tree, attachment registry, evidence index, Workframe mounts, or agent permissions. Their exclusion is an explicit constitutional boundary, not a hidden ignore pattern.

## 4. Architectonic manifest

Illustrative excerpt:

```json
{
  "protocol": "architectonic",
  "instance": "northstar-practice-learning",
  "profile": "full",
  "layers": [
    "constitution",
    "doctrine",
    "identity",
    "project",
    "rail",
    "skills",
    "knowledge",
    "agents",
    "meta"
  ],
  "local_root": "organization",
  "projects": [
    {
      "id": "september-seminar",
      "root": "projects/september-seminar",
      "ledger_root": "projects/september-seminar/operations/ledger.json"
    },
    {
      "id": "public-website",
      "root": "projects/public-website",
      "ledger_root": "projects/public-website/operations/ledger.json"
    },
    {
      "id": "research-library",
      "root": "projects/research-library",
      "ledger_root": "projects/research-library/operations/ledger.json"
    }
  ]
}
```

The `full` profile is justified in this example because purpose, constitutional privacy, actor authority, several projects, a shared corpus, multiple agents, Rails, and upkeep all interact. A smaller user outcome would install fewer layers.

## 5. Constitution excerpt

```markdown
# Constitution

## Human authority root

Mara is the final human authority for Northstar Practice & Learning.
No agent, runtime, collaborator, or automated loop may override her stop decision.

## Absolute clinical-data prohibition

Patient-identifiable information, clinical records, patient communications,
appointment notes, diagnostic material, billing records containing patient identity,
and any folder designated as clinical are outside AI access.

This prohibition applies to local scanning, metadata inventory, content extraction,
external model processing, Workframe mounts, copied snapshots, embeddings, logs,
and generated summaries.

## External effects

Agents may draft public material. Publication, outbound messaging, deployment,
purchasing, subscription changes, and credential changes require explicit approval.

## Permission escalation

Agents may not grant themselves or other agents additional access. New grants require
Mara or an explicitly designated human administrator.

## Amendment

Constitutional amendments require an explicit diff, stated reason, and confirmation
from Mara. The clinical-data prohibition cannot be weakened through an agent-only action.
```

## 6. Doctrine excerpt

```markdown
# Doctrine

- Use evidence before inference.
- Preserve uncertainty rather than manufacturing professional certainty.
- Prefer the smallest useful automation.
- Keep clinical judgment and protected information outside this system.
- Draft freely inside approved scopes; require approval at public, financial,
  credential, deployment, and destructive boundaries.
- Use source material to ask better questions rather than forcing a generic template.
- Keep public education clear about where evidence ends and interpretation begins.
- Stop when the next step would require excluded data or professional judgment the
  system is not authorized to make.
```

## 7. Project organization

### 7.1 September seminar

**Purpose:** create a source-grounded professional seminar for September.  
**Repositories:** none required.  
**Attachments:** existing seminar folder read-write; professional research folder read-only; prior seminar copied as a dated snapshot.  
**Rail:** required because research, outline, review, slide production, and final approval span several sessions and roles.

### 7.2 Public website

**Purpose:** maintain accurate public information and publish approved educational content.  
**Repositories:** one Git repository cloned into `repositories/public-website/`.  
**Attachments:** approved public biography extract and brand assets; no private practice records.  
**Rail:** required because content, code, review, deployment, and approval cross roles.

### 7.3 Research library

**Purpose:** curate public and licensed professional sources relevant to education and non-clinical work.  
**Repositories:** none.  
**Attachments:** professional research folder read-only.  
**Rail:** used for source review, contradiction resolution, and periodic retirement; it is not automatically a living-knowledge loop until cadence, verification, and budget are approved.

## 8. Attachment registry

Illustrative entries:

```json
[
  {
    "id": "seminar-materials",
    "project_ids": ["september-seminar"],
    "mode": "mount_read_write",
    "source": "~/Documents/Seminar 2026",
    "workspace_path": "mounted/seminar-materials",
    "authority": "Mara-owned",
    "sensitivity": "internal",
    "external_processing": "approved excerpts only",
    "mutation": "project agents with write grant",
    "refresh": "live"
  },
  {
    "id": "professional-research",
    "project_ids": ["september-seminar", "research-library"],
    "mode": "mount_read_only",
    "source": "~/Documents/Professional Research",
    "workspace_path": "mounted/professional-research",
    "authority": "mixed sources; per-source provenance required",
    "sensitivity": "internal",
    "external_processing": "per-item approval",
    "mutation": "forbidden",
    "refresh": "live"
  },
  {
    "id": "website-repository",
    "project_ids": ["public-website"],
    "mode": "clone_repository",
    "source": "git@example.org:mara/public-site.git",
    "workspace_path": "repositories/public-website",
    "authority": "canonical source repository",
    "sensitivity": "internal source / public output",
    "external_processing": "approved runtime adapters",
    "mutation": "web-maintainer and reviewer scopes",
    "refresh": "git"
  },
  {
    "id": "previous-seminar-2025",
    "project_ids": ["september-seminar"],
    "mode": "copy_snapshot",
    "source": "~/Archives/Seminar 2025",
    "workspace_path": "snapshots/previous-seminar-2025",
    "authority": "historical reference, not current doctrine",
    "sensitivity": "internal",
    "external_processing": "selected excerpts",
    "mutation": "snapshot immutable",
    "refresh": "none"
  }
]
```

## 9. Team and agent topology

```text
Human owner: Mara
|
+-- Concierge agent
|   +-- runtime: Claude Code authenticated session, used in place
|   +-- organization-wide read access to approved doctrine
|   +-- project routing and Socratic clarification
|   +-- no publication, spending, deployment, or permission changes
|
+-- Research agent
|   +-- runtime: Hermes profile using Workframe-brokered model access
|   +-- read-only access to research attachments
|   +-- may create evidence reports and propose source updates
|   +-- may not edit canonical doctrine directly
|
+-- Editor agent
|   +-- runtime: Claude Code
|   +-- write access to seminar draft files
|   +-- may not publish or represent drafts as approved professional advice
|
+-- Web maintainer agent
|   +-- runtime: Codex CLI authenticated through the user's account
|   +-- write/test access to public-website repository
|   +-- no deploy, merge, or credential authority
|
+-- Reviewer agent
    +-- runtime: separate Hermes profile/model policy
    +-- read access across project outputs and sources
    +-- may approve Rail review gates according to policy
    +-- may not approve public publication on Mara's behalf
```

Specialist agents exist because their responsibilities and review boundaries recur. A smaller initial installation could begin with only the concierge and add others later.

## 10. Permission matrix

| Capability | Mara | Concierge | Research | Editor | Web maintainer | Reviewer |
|---|---:|---:|---:|---:|---:|---:|
| Read organization doctrine | Yes | Yes | Scoped | Yes | Scoped | Yes |
| Read clinical data | No through system | No | No | No | No | No |
| Read research mount | Yes | Yes | Yes | Scoped | No | Yes |
| Write seminar materials | Yes | Propose | No | Yes | No | Review comments |
| Write website repository | Yes | Propose | No | No | Yes | Review comments |
| Modify constitution | Yes | Propose diff | No | No | No | Review only |
| Create/change agents | Yes | Request | No | No | No | No |
| Change permissions | Yes | No | No | No | No | No |
| Use web research | Yes | Yes | Yes | Yes | Yes | Yes |
| Spend money | Yes | No | No | No | No | No |
| Publish externally | Yes | No | No | No | No | No |
| Deploy website | Yes/approve | No | No | No | Prepare only | Verify only |
| Stop any agent | Yes | Stop own run | Stop own run | Stop own run | Stop own run | Stop own run |

Actual enforcement comes from Workframe grants and runtime profiles, not from this table alone.

## 11. Model and funding policy

```json
{
  "default": {
    "funding": "user_account",
    "external_processing": "approved sources only",
    "fallback": "deny_and_ask",
    "silent_provider_reroute": false
  },
  "agents": {
    "concierge": {
      "runtime": "claude-cli",
      "auth": "use_in_place",
      "model_policy": "account-default within disclosed usage"
    },
    "web-maintainer": {
      "runtime": "codex-cli",
      "auth": "use_in_place",
      "sandbox": "project-write",
      "network": "documented runtime behavior"
    },
    "research": {
      "runtime": "hermes",
      "provider": "workframe-vault",
      "funding": "workspace-funded with monthly cap",
      "budget_usd_monthly": 25
    }
  }
}
```

If the configured provider is unavailable, Workframe denies the run and asks for a permitted alternative. It does not silently route sensitive context to another provider.

## 12. Project Rail examples

### 12.1 Seminar Rail item

```json
{
  "id": "SEMINAR-014",
  "title": "Produce source-grounded first outline",
  "project": "september-seminar",
  "status": "ready",
  "eligible_roles": ["research", "editor"],
  "dependencies": ["SEMINAR-008", "SEMINAR-011"],
  "scope": {
    "read": ["mounted/professional-research", "snapshots/previous-seminar-2025"],
    "write": ["mounted/seminar-materials/drafts"]
  },
  "required_evidence": [
    "claim-to-source table",
    "explicit unresolved claims",
    "list of excluded clinical domains"
  ],
  "review": {
    "required_role": "reviewer",
    "human_approval": false
  },
  "completion": "Outline file exists, sources resolve, reviewer accepts evidence discipline"
}
```

### 12.2 Website Rail item

```json
{
  "id": "WEB-006",
  "title": "Update public seminar page",
  "project": "public-website",
  "status": "blocked",
  "eligible_roles": ["web-maintainer"],
  "dependencies": ["SEMINAR-021"],
  "required_evidence": ["local build", "content diff", "link check"],
  "review": {
    "required_role": "reviewer",
    "human_approval": true,
    "approval_reason": "public publication and deployment boundary"
  }
}
```

Each project has exactly one Rail ledger. Workframe boards and status views project from those ledgers; they do not become competing queues.

## 13. Workframe mapping

```text
Workframe workspace: Northstar
|
+-- Owner/admin: Mara
|
+-- Space: Organization
|   +-- purpose, constitution, doctrine, decisions
|   +-- concierge agent
|
+-- Space: September Seminar
|   +-- seminar files
|   +-- seminar Rail
|   +-- research, editor, reviewer agents
|
+-- Space: Public Website
|   +-- repository files and preview
|   +-- website Rail
|   +-- web-maintainer and reviewer agents
|
+-- Space: Research Library
    +-- read-only source browser
    +-- research Rail
    +-- research and reviewer agents
```

The Workframe UI exposes chat, files, source previews, project Rails, agent routes, approvals, artifacts, and activity. The Architectonic files remain the durable contract beneath those views.

## 14. Runtime bindings

### Claude Code

Used in place through the existing authenticated CLI. It receives runtime-specific project instructions generated from the canonical Architectonic files. Its private auth files are not copied into Workframe.

### Codex CLI

Used for the website project through a restricted project write scope. Workframe records the runtime and model attribution for completed turns. Codex cannot read the research or seminar mounts because they are outside its grants.

### Hermes

Runs persistent research and reviewer profiles inside Workframe. Provider credentials remain in the Workframe vault; profiles receive bounded lease tokens. Hermes session history is useful execution state but does not outrank project files.

## 15. Generated startup context

When Mara opens a fresh session with the seminar concierge, the agent receives:

```text
You are the concierge for Northstar Practice & Learning.

Human owner and stop authority:
- Mara

Organization purpose:
- Support non-clinical professional education, research, communication,
  and administration without exposing patient-identifiable information.

Current project:
- September Seminar

Current objective:
- Produce a source-grounded seminar outline.

Absolute prohibition:
- Do not inspect, request, index, summarize, transmit, or infer from clinical
  records or patient-identifiable information.

Canonical read order:
1. organization/CONSTITUTION.md
2. organization/AUTHORITY.md
3. organization/PRIVACY.md
4. projects/september-seminar/START_HERE.md
5. projects/september-seminar/project_profile.md
6. projects/september-seminar/operations/ledger.json

Rail:
- projects/september-seminar/operations/ledger.json

Known blocking unknown:
- Whether the seminar will include a section on AI-assisted administration.

Permissions:
- Read approved seminar and research sources.
- Propose project-file changes.
- Route bounded work to installed project agents.
- Do not publish, spend, change permissions, or access excluded folders.
```

A new session can therefore continue immediately without asking Mara to reconstruct the organization, project, privacy boundary, source set, agents, or current work.

## 16. Verification result

```text
Architectonic manifest                    PASS
Organization purpose and doctrine         PASS
Constitution authority root               PASS
Clinical-data exclusion                   PASS
Source attachments and provenance         PASS
Repository clone integrity                PASS
One Rail per active project               PASS
No competing authored queues              PASS
Agent owners and stop rights               PASS
Project and organization permissions      PASS
Claude use-in-place adapter                PASS
Codex project-scope adapter                PASS
Hermes vault lease path                    PASS
Workframe health and room binding          PASS
Fresh-session startup context              PASS
Unresolved questions preserved             PASS
```

## 17. Final user outcome

Mara does not end with a database record that says `privacy_concern=true`. She ends with:

- an explicit purpose;
- a constitutional privacy prohibition;
- a governed organization and team;
- three bounded projects;
- repositories and folders attached in different approved modes;
- source provenance and known unknowns;
- one Rail per active project;
- agents with distinct roles and permissions;
- Claude, Codex, and Hermes attached through separate runtime policies;
- a Workframe workspace that presents the same durable system;
- a new-session entry point that restores useful context without relying on hidden memory.

That is the intended fully installed and instantiated Workframe Origin outcome.
