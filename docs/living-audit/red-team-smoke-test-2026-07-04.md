# Red-team smoke test — 2026-07-04

## Purpose

Verify that the temporary Workframe Red Team rail can write compact planning material under `docs/living-audit/` without touching product source code.

## Inspected source evidence

- `README.md` confirms public install docs still point at `create-workframe@0.1.6`.
- `AGENTS.md` confirms repository mutation discipline and source hierarchy.
- `START_HERE.md` confirms `operations/log.md` as the repository ledger and identifies known failing scenarios.
- `.harness/README.md` confirms Workframe has a product operator ledger but uses ABKB for cross-repo assignments.
- `docs/living-audit/README.md` already exists and contains the first installer decision-tree planning pass.

## Challenged assumption

The planning rail can safely assume `docs/living-audit/` exists and is writable. That is now verified for the planning rail. This smoke test verifies the complementary red-team write pattern.

## Red-team finding

The first planning pass already surfaced one concrete drift: public README install commands still use `create-workframe@0.1.6`, while package metadata inspected earlier showed `0.1.7`. This should stay in the living audit as release-readiness evidence, not be patched during the planning phase.

## Constraint

The temporary 12-hour rails should only create/update planning files and append log entries. They should not edit installer code, package metadata, API code, UI code, or Docker compose during this phase.

## Next red-team target

Review whether the installer decision tree over-assumes safe detection of existing runtimes and credentials. The next red-team pass should focus on destructive adoption risk: host Hermes, Claude CLI, Codex auth, Cursor, Docker volumes, provider keys, and existing generated Workframe installs.
