# WF-039 — Domain model package

## Problem

Cell, run, lease, and agent concepts live implicitly in `server.py`, SQLite DDL, and Hermes profile slug conventions. API, UI, and future adapters need one typed vocabulary.

## Outcome

Python dataclasses + JSON schema under `services/workframe-api/domain/`.

## Entities

| Entity | Purpose |
|--------|---------|
| `Cell` | Install/deployment unit |
| `User` | Workspace member |
| `Workspace` | Team scope inside a cell |
| `AgentIdentity` | Persistent agent (not Hermes profile) |
| `RuntimeBinding` | Agent → runtime link |
| `Run` | Authority + economics unit |
| `RunEvent` | Ledger event |
| `Lease` | Scoped credential token for a run |
| `Grant` | Capability granted to a run |
| `CredentialRef` | Vault pointer (no secrets) |

## Artifacts

| Path | Role |
|------|------|
| `services/workframe-api/domain/entities.py` | Dataclasses + enums |
| `services/workframe-api/domain/schema/workframe-domain.schema.json` | JSON Schema `$defs` |
| `services/workframe-api/domain/__init__.py` | Public import surface |
| `services/workframe-api/test_domain_entities.py` | Round-trip self-check |
| `docs/public/glossary.md` | Public vocabulary (WF-NS-P0) |

## Consumers (planned)

| Item | Usage |
|------|-------|
| WF-009 RunAuthorityGate | `Run`, `Grant`, `Lease`, `CredentialRef` |
| WF-NS-P2 runs tables | `Run`, `RunEvent` column mapping |
| WF-007 CellAuthorityGate | `Cell` |
| WF-010 SurfaceContractGate | `RunSurface` |

## Non-goals

- No `server.py` migration in this item
- No `packages/domain` npm package (WF-038 pruned stubs; API owns Python domain)

## Verify

```bash
cd services/workframe-api
python test_domain_entities.py
python -m py_compile domain/entities.py domain/__init__.py
```

## Acceptance

See `backlog.json` → `WF-039.acceptance`.
