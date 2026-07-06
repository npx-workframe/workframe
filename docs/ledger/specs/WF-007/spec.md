# WF-007 — CellAuthorityGate (design)

## Problem

`workframe-manifest.json` exists at install time but is not yet an authority. Users can confuse manifest presence with safe open/update/connect/adopt. Default `npx create-workframe MyProject` can be destructive on an existing directory (WF-004).

## Principle

```text
manifest_present != cell_authority
cell_authority = manifest + provenance + ownership + health + negative-write guarantees
```

## Domain inputs (WF-039)

| Type | Role in gate |
|------|----------------|
| `Cell` | `cell_id`, `install_root`, `manifest_path`, `package_version`, `deployment_mode`, provenance fields |
| `Grant` | Optional cell-scoped capability (`file_write` on install root, `runtime_exec` for adopt) |
| `CredentialRef` | Not used at cell layer except remote-connect attestation (future) |

## Operations

### 1. Create (install)

| Check | Rule |
|-------|------|
| Target empty | Only empty directory or explicit `--force` with mutation evidence (WF-019) |
| Provenance | Record `package_version`, `packed_artifact_digest`, `git_ref` on `Cell` |
| Manifest write | Atomic write of `workframe-manifest.json` last |
| Deny | Non-empty target without authority → no filesystem mutation |

**Implementation ticket:** `WF-019` NegativeInstallEvidence runner; wire `create-workframe` to emit `Cell` provenance.

### 2. Open (read-only)

| Check | Rule |
|-------|------|
| Ownership | Resolved `install_root` matches manifest `layout.install_root` |
| Provenance drift | Package version in manifest matches last recorded evidence or flag `stale` |
| Health | Docker compose status, API `/api/health`, supervisor reachability (read-only probes) |
| Mode | Deployment mode from `stack_config.json` matches manifest security section |

**Outcome:** `allow_readonly` or `deny` with reason. No profile mutation, no compose up/down, no vault writes.

**Implementation ticket:** `WF-008` mutation-free doctor JSON feeds open checks.

### 3. Update (package upgrade)

| Check | Rule |
|-------|------|
| Open checks | All read-only open checks pass |
| Backup | Require backup manifest reference or explicit user ack |
| Dry-run | Migration plan diff (file list, compose service changes) before apply |
| Authority | Explicit user/admin consent; supervisor token for profile-touching steps |

**Outcome:** `allow_update` with mutation plan artifact, or `deny`.

**Implementation ticket:** extend `updates.py` to consult gate; block without plan.

### 4. Connect (remote cell)

| Check | Rule |
|-------|------|
| Remote attestation | TLS, invite policy, displayed execution boundary |
| Local cell | Remote `Cell` record separate from local install root |
| Credentials | No host credential import without `RuntimeBinding` candidate flow (WF-014 deferred) |

**Outcome:** `allow_connect_readonly` or `deny`.

### 5. Adopt runtime (deferred)

Blocked until WF-014/NS-P4. Gate returns `deny` with `adapter_not_proven` for non-Hermes candidates.

## Decision shape (planned API)

```python
@dataclass(frozen=True)
class CellAuthorityDecision:
    operation: Literal["create", "open", "update", "connect", "adopt"]
    decision: Literal["allow", "allow_readonly", "deny", "needs_user_action"]
    reason: str
    cell: Cell | None
    mutation_plan: list[str]  # empty when deny or read-only
```

Not implemented in this stage — types live in this spec until WF-007 implementation lane.

## Mutation plan

Before any mutating operation, emit an ordered plan:

```text
1. assert install_root writable
2. snapshot manifest digest
3. apply bounded mutations (enumerated paths)
4. verify health
5. record evidence artifact
```

Rollback reference stored alongside plan. WF-019 proves **zero** steps execute on deny.

## UI / product rules

- Files panel shows locked state when open is read-only (`CellAuthorityGate` deny mutation).
- Install docs: empty target only until update path is proven (WF-004).
- Doctor/preflight lists missing prerequisites without mutating host (WF-008).

## Implementation tickets (derived)

| ID | Scope |
|----|-------|
| WF-007-impl | `cell_authority.py` module + unit tests |
| WF-019 | Negative install evidence (create deny) |
| WF-008 | Doctor JSON for open health |
| WF-004 | Public docs + empty-target claim alignment |

## Dependencies

- **WF-039** `Cell` type — done
- **WF-019** — negative create evidence
- Do **not** implement adopt until WF-014/NS-P4

## Acceptance (backlog)

- [x] Design doc committed (this file)
- [x] Implementation tickets derived (table above)
- [ ] Update/connect/adopt blocked without explicit authority (implementation)

## Sources

- `archive/planning/living-audit/red-team-08-manifest-authority-risk.md`
- `archive/planning/living-audit/final-convergence-synthesis.md`
- WF-039 `domain/entities.py` → `Cell`
