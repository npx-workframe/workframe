# WF-002 — PackageTruthGate

## Problem

Green CI on source does not prove the **installable npm package** works. Release trust requires evidence from `npm pack` → clean install → health → first chat.

## Outcome

A repeatable runner produces `PackageInstallEvidence` JSON that release sign-off consumes. Fails on version drift, missing UI bundle, or broken generated compose.

## Why now

Blocks P0 findings WF-001, WF-005, WF-006 and north-star wedge “one boring managed-Hermes path.”

## Non-goals

- Second runtime adapters
- Public VPS marketing claims
- Host Hermes adoption

## Acceptance

See `backlog.json` → `WF-002.acceptance`.

## Sources

- `archive/planning/living-audit/package-truth-gate.md`
- `archive/planning/living-audit/25-audit.md` (P0-2, ticket-2)
