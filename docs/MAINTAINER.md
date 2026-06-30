# Documentation layout

## `docs/public/` (tracked — publishable)

Code-grounded docs safe for GitHub and docs.workfra.me. No maintainer paths, tenant hostnames, or internal codenames.

When updating public docs, verify against:

- `services/workframe-api/server.py`
- `services/workframe-supervisor/server.py`
- `apps/web/src/`
- `infra/compose/workframe/`

## `docs/private/` (gitignored — local only)

Operator runbooks, audit working notes, publish checklists with environment-specific detail. Not pushed to GitHub.

Create this folder locally as needed. Nothing here is required to install or audit the product from source.

## `docs/archive/` (gitignored — local only)

Historical audits, strategy drafts, session handoffs, and superseded design docs. Kept for maintainer reference; never publish.

If you need to recover archived material after a fresh clone, check your team's private knowledge base or local backups.

## Installer docs

`packages/create-workframe/docs/workspace-instructions/` is copied into generated projects via npm pack. Keep it user-facing and concise.

## Sanitization rules (public)

- No local filesystem paths (`/opt/...` in deploy docs is OK; drive letters are not)
- No personal hostnames or tenant IDs
- No internal project codenames
- No event-specific or time-bound marketing narrative in product docs
- Code citations beat prose when behavior is non-obvious
