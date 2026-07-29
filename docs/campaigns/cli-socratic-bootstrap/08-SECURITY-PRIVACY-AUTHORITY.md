# Security, Privacy, and Authority

## 1. Security objective

Workframe Origin must be active enough to discover useful context and conservative enough not to become surveillance, credential theft, uncontrolled indexing, or an authority-escalation mechanism.

The security model is based on a strict separation:

```text
presence      what exists
access        what can technically be read or invoked
consent       what the user has authorized for a stated purpose
processing    what may be computed locally or externally
mutation      what may be changed
operational authority  what an actor may do in a project or organization
```

None of these states implies the next.

## 2. Threat model

### 2.1 Accidental overreach

The installer scans too broadly, reads private folders, follows links outside scope, expands archives, or transmits more content than the user understood.

### 2.2 Credential exposure

The system prints environment values, scrapes runtime token stores, logs secrets, injects keys into shared profiles, or distributes a hosted provider key.

### 2.3 Model-generated mutation

A model produces a path, command, manifest, or permission change that is accepted without deterministic validation.

### 2.4 Prompt injection from local sources

An inspected document attempts to change system instructions, request secrets, expand scan scope, invoke tools, or authorize external effects.

### 2.5 Authority confusion

The system infers that a user owns a document, may change a repository, represents an organization, or can expose another person's data merely because the file is locally readable.

### 2.6 Sensitive-domain leakage

Protected clinical, legal, financial, employment, family, or client information enters an evidence index or external inference request without valid scope and purpose.

### 2.7 Silent persistence

Private content is copied into the generated knowledge base, embeddings, logs, backups, or Workframe files when a reference or local-only analysis would have been sufficient.

### 2.8 Agent permission escalation

An installed agent creates another agent, broadens a mount, imports a credential, changes project scope, spends, publishes, deploys, or modifies constitutional rules without authorized approval.

### 2.9 Confused deputy

Workframe or a runtime executes a technically valid action using credentials or authority belonging to another user, project, organization, or funding scope.

### 2.10 False confidence

Generated doctrine appears authoritative despite being based on incomplete, stale, contradictory, or probabilistically classified sources.

## 3. Progressive consent model

Consent is capability-specific, purpose-specific, and scope-specific.

### Level 0 — process start

Permits only CLI execution and fixed local status rendering.

### Level 1 — host discovery

Permits allowlisted version and status probes. No user-document access.

### Level 2 — root and repository metadata

Permits listing approved roots and detecting repositories through metadata.

### Level 3 — file inventory

Permits names, paths, type, size, timestamps, and hashes within approved scopes.

### Level 4 — local content processing

Permits reading selected contents locally. No external transmission.

### Level 5 — external inference

Permits exact evidence IDs or excerpts to reach an approved adapter/provider.

### Level 6 — attachment

Permits reference, mount, copy, extract, adoption, or clone according to an explicit mode.

### Level 7 — mutation

Permits validated writes to exact destinations and operation classes.

### Level 8 — operational authority

Permits installed humans or agents to act within organization/project scopes after setup.

Each grant records:

```text
grant id
capability
subject
scope
purpose
data class
processing location
runtime/provider
mutation level
funding source
issued by
issued at
expiry
revocation status
parent grant
```

## 4. Consent interaction rules

- Sensitive grants never use preselected defaults.
- Silence, confusion, or unrelated natural language is not consent.
- A model may interpret the user's answer, but deterministic code must display the resulting grant.
- Bundled consent is prohibited when the component capabilities have materially different risks.
- “Read this folder” does not imply permission to transmit it.
- “Use Claude” does not imply permission to expose all inspected files to Claude.
- “Set this up” does not imply permission to overwrite, move, delete, deploy, spend, publish, or invite users.
- Consent can be narrowed before it is broadened.
- Revocation must be available after installation.

## 5. Runtime authentication

### 5.1 Use authenticated CLIs in place

Preferred behavior:

```text
Workframe Origin
  -> invokes documented CLI command
  -> CLI uses its own authentication store
  -> Workframe Origin receives bounded output/receipt
```

Prohibited behavior:

- reading private auth databases;
- copying browser sessions;
- parsing undocumented token caches;
- converting subscription authentication into a reusable API key;
- importing authentication merely because its files are readable.

### 5.2 Environment keys

The system may detect the presence of allowlisted variable names. It must not print values. Use in place requires permission. Import to a vault is a separate grant.

### 5.3 New keys

New credentials use hidden input, validation after consent, encrypted storage, and a receipt that names the provider without storing the key in formation logs.

### 5.4 Hosted fallback

A Workframe-funded adapter must:

- retain the master key server-side;
- issue short-lived formation-session authorization;
- enforce a model allowlist;
- enforce per-session and per-account budgets;
- rate limit and detect abuse;
- record usage receipts;
- state the provider and data path;
- support revocation;
- reject general-purpose proxy use outside the campaign scope.

## 6. Filesystem safety

### 6.1 Scope normalization

All granted paths are resolved to canonical OS paths. The scanner detects symlinks, junctions, aliases, mount points, and path traversal. A link escaping scope is denied unless separately granted.

### 6.2 Existing paths

An existing target produces one of:

```text
inspect
reopen
adopt
attach
repair
create elsewhere
explicit replace
```

It never produces silent scaffold overwrite.

### 6.3 Ignore and stop rules

Default exclusions include:

- version-control internals not required for metadata;
- dependency directories;
- build outputs;
- caches;
- secret stores;
- browser profiles;
- keychains;
- system directories;
- known clinical/medical record locations when declared;
- hidden content unless explicitly included;
- archives unless explicitly opened;
- cloud placeholders that require download unless approved.

Sensitive-path heuristics stop and ask. They do not silently expand access.

### 6.4 Write compiler

Model output is compiled into a restricted mutation plan. The compiler validates:

- operation type;
- destination under approved root;
- current file state;
- expected content hash when updating;
- schema;
- source provenance;
- authority;
- backup/checkpoint;
- rollback behavior.

No raw model shell command executes directly.

## 7. Prompt-injection defense

Local and remote sources are untrusted data.

The extraction layer must:

- label source content as evidence, not instruction;
- prevent source text from modifying grants or system policy;
- strip or neutralize tool-call markup where appropriate;
- reject requests inside sources to reveal secrets or broaden scope;
- separate source excerpts from orchestration instructions;
- record suspected injection attempts;
- require deterministic authority for any operation.

A source may state a policy, but it does not become governing doctrine merely because it contains imperative language.

## 8. Privacy classification

Recommended classes:

| Class | Default handling |
|---|---|
| `public` | May be processed by approved adapters within purpose. |
| `internal` | Local by default; external processing requires grant. |
| `confidential` | Exact source-level grant; minimize retention and excerpts. |
| `local_only` | Never sent externally; may be processed by approved local runtime if explicitly allowed. |
| `excluded` | No inventory, content read, attachment, or inference. |
| `regulated_or_third_party` | Stop and establish ownership, lawful authority, purpose, and processing boundary before access. |
| `secret` | Never enters chat, evidence text, generated files, or ordinary logs. Use secret-store interfaces only. |

Classification may be proposed probabilistically but must not reduce protection without user confirmation.

## 9. Authority layers

### 9.1 Human authority

The system must establish a human authority root or explicitly preserve that it is unresolved. Organizational roles may have scoped authority, but every operational agent must have a human owner and stop path.

### 9.2 Organization authority

Organization-wide grants govern shared doctrine, user management, agent creation, workspace funding, and cross-project policy.

### 9.3 Project authority

Project grants govern sources, repositories, Rails, tools, models, and external effects within the project.

### 9.4 Runtime authority

Runtime capabilities are bounded by adapter controls and Workframe grants. A capable runtime is not automatically permitted to use every capability it supports.

### 9.5 Agent authority

Installed-agent files describe intended role. Enforced grants determine actual authority. Agents cannot grant themselves new permissions.

### 9.6 Delegation

Delegation must obey:

```text
delegated scope <= delegator scope
budget <= delegator budget
expiry <= delegator expiry
prohibitions remain inherited
human/administrative gates remain required
```

## 10. Workframe credential and execution boundary

The campaign should retain Workframe's separation between general agent egress and secret-mediated actions.

```text
runtime
  ├─ general public internet research
  └─ brokered credential actions
       -> Workframe lease validation
       -> vault
       -> upstream provider/action
```

Raw vault secrets should not be mounted into shared runtime containers or profiles. Per-user and per-project scope must be validated at the broker.

Existing authenticated CLI adapters may remain outside the vault but must be bound to the correct local user and project scope.

## 11. External processing receipts

Every externally processed request should record:

```text
request id
formation/project id
adapter
provider
model when known
data class
source evidence ids
redaction policy
purpose
funding source
token/cost usage when available
started/completed time
result status
```

Receipts do not contain secret values or unnecessary raw content.

## 12. Persistence and minimization

### Persist

- grants and revocations;
- evidence references and hashes;
- accepted claims and decisions;
- unresolved unknowns and contradictions;
- approved doctrine;
- source attachment metadata;
- transaction receipts;
- verification results;
- runtime and agent bindings.

### Avoid persisting by default

- raw chat transcripts;
- full copies of private source trees;
- arbitrary model prompts and responses containing private content;
- credentials;
- browser/session stores;
- temporary extraction buffers;
- rejected inferences;
- unrelated machine inventory.

## 13. Audit and transparency

The user must be able to answer:

- What did the system detect?
- Which folders did it list?
- Which files did it read?
- Which excerpts left the machine?
- Which provider/model received them?
- What did the model infer?
- Which claims did I confirm?
- Which files were written?
- Which repositories were cloned or adopted?
- Which mounts are active?
- Which agents have which permissions?
- Which credentials and funding scopes are in use?
- How do I revoke or delete each item?

Audit views must be understandable in simple mode and exact in expert mode.

## 14. Revocation

Revocation types:

```text
inference adapter disable
provider key deletion or rotation
source read grant revoke
external processing grant revoke
mount detach
copied snapshot delete or archive
repository runtime write revoke
agent disable
project membership revoke
workspace funding revoke
formation state archive/delete
Workframe deployment shutdown
```

Revoking future access does not silently erase accepted canonical doctrine. Deleting or retracting derived claims is a separate reconciliation operation that preserves history and provenance where appropriate.

## 15. Safe failure behavior

On uncertainty or failure, default behavior is:

- stop the affected operation;
- retain no new authority;
- preserve the last verified checkpoint;
- state what completed and what did not;
- avoid retrying with broader scope or another provider silently;
- offer deterministic recovery options;
- leave existing user files untouched unless an applied transaction is verified.

## 16. Security acceptance criteria

- Zero model calls before an inference grant.
- Zero external content transmissions outside explicit evidence scope.
- Zero secret values in logs, generated Markdown, or receipts.
- Zero runtime-auth scraping.
- Zero silent overwrites.
- Zero path traversal outside granted roots.
- Zero source-driven changes to permissions or system policy.
- Zero installed agents without a human owner and stop authority.
- Zero project agents receiving organization-wide access by default.
- Zero silent provider fallback.
- Zero duplicate Rail authorities per project.
- Every mount and clone has provenance and revocation instructions.
- Every external request has a redacted receipt.
- Every material mutation has a checkpoint and read-back verification.
