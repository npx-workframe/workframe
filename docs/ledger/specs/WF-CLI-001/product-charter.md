# WF-CLI — Socratic CLI product charter

**Campaign:** WF-CLI · **Canonical plan:** `campaign.json` · **Work authority:** `ledger.json`

## What this is

The standalone `workframe` npm package is a **Socratic CLI** that helps a human define an entity—project, organization, or venture—through conversation, then **instantiates Architectonic** (constitution, doctrine, agents, layer contracts) and, when explicitly chosen, a **Workframe cell** (install, connect, or deploy). It is not a second product queue, not a cloud fallback, and not a shortcut past authority gates.

The CLI ships as a small Node binary (`status`, `help`, `version`, then `begin` and later commands). It must remain usable **without** installing Workframe, adopting a runtime, or mutating any existing setup.

## Voice

- **One question at a time.** No questionnaires, no walls of options, no implied consent from silence.
- **Mirror before you architect.** Reflect what was stated; mark what is unresolved; never silently reinterpret hedged language as a fact or a provider selection.
- **Plain language.** Explain payer, credential class, and authority in human terms before any billable or destructive step.
- **Interruptible.** EOF, Ctrl+C, timeout, refusal, and empty answers end cleanly—no orphan children, no leaked diagnostics, no credential echo.
- **Machine-readable when asked.** `--json` output is stable, bounded, and free of ANSI or secret material.

## Rail-first

Work advances through **one ledger-owned slice** at a time (`WF-CLI-001` … `WF-CLI-008`). Each slice has acceptance criteria, evidence targets, and explicit `depends_on` links. Implementation follows Rail discipline: bind role → smallest coherent patch → verify at source → record evidence → stop at the role boundary. Review, publication, and apply are separate gates—not features of `begin`.

`campaign.json` is the campaign plan; `ledger.json` is the single work authority. Spec-kit depth (`spec.md`, this charter, per-item stubs) elaborates without forking status.

## Ponytail slices (the chain)

Big-bang “Socratic bootstrap” branches are rejected evidence. The campaign is deliberately thin:

| Slice | Intent |
|-------|--------|
| **001** | Memory-only `begin`—deterministic questions, bounded mirror, stated/unresolved provenance. No model, no credential read, no filesystem write. |
| **002** | Truthful capability graph—installed ≠ authenticated ≠ verified; no inference. |
| **003** | Provider-neutral dialogue + cancellable verification behind separate consent; carries archived inference regressions from rejected PRs. |
| **004** | Constitutional entity draft in memory—authority, goals, constraints, provenance per field. |
| **005** | Non-destructive Architectonic composition plan—inventory, additive paths, collision refusal. |
| **006** | Dry-run Workframe deployment plan—observe capabilities; never invoke `create-workframe`. |
| **007** | Apply and rollback authority gates—immutable plan hash, explicit approval, simulation only. |
| **008** | Packed cross-platform evidence—npm pack matrix; publication remains a separate release decision. |

Each slice is the minimum code that works. **Shipped in `workframe@0.3.0`** (dry-run chain; real apply and npm publish remain gated). Deletion over addition. No unrequested abstractions in `packages/workframe`.

## What Architectonic + Workframe mean here

**Architectonic** is the layered doctrine stack: north star, constitution, agent roles, skills, and contracts that describe how software in the org should behave. The CLI proposes **additive** layer files and agent definitions from a confirmed draft—never overwrite, adopt, or merge-review without an explicit later apply gate.

**Workframe** is the optional runtime cell: Docker Hermes, BFF, UI, brokers, run ledger. The CLI may **recommend** local, Docker, or VPS deployment from observed host facts. Installing, updating, or connecting to an existing cell requires a reviewed immutable plan and a separate authority gate—not an opportunistic side effect of conversation.

## Invariants (non-negotiable)

- No credential values in stdout, stderr, JSON, plans, or tests.
- No implicit cloud or Workframe-hosted inference fallback.
- No merge or rebase of `origin/automation/wf-cli-001-*` branches.
- `WF-CLI-002` does not start until `WF-CLI-001` is independently accepted.
- Publication to npm is a reviewed release decision, not an acceptance criterion for a slice.

## Success

A human runs `npx workframe begin`, answers six honest questions, receives a bounded mirror they recognize as theirs, and—only in later slices—sees truthful capability facts, optional model assistance with cancellable verification, a constitutional draft, Architectonic and Workframe plans they can reject or approve, and packed evidence that nothing was mutated without consent. The cell they get (if any) matches what they explicitly approved.
