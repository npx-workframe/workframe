# Ponytail Pass — Minimal Build Contract

## Finding

The research campaign is useful as a possibility map, but it is too large to serve as an implementation contract. It specifies full-disk discovery, hosted inference fallback, source ingestion, ontology compilation, project organization, Rail creation, agent teams, Workframe deployment, multi-runtime attachment, security policy, and ongoing knowledge maintenance before proving that a user benefits from the first five minutes.

The implementation branch treats the long campaign documents as **research reference only**. The canonical build contract is this file, the Spec Kit feature under `specs/001-origin-minimal-bootstrap/`, and the branch Rail.

## Ponytail ladder

1. **Does it need to exist?** The continuity problem is real; a small bootstrap entrypoint is justified.
2. **Does it already exist?** Runtime and provider discovery already exists in `packages/workframe/bin/workframe.js`. Reuse it.
3. **Does Architectonic already do it?** Composition, onboarding, verification, maps, agents, and Rail scaffolding belong to Architectonic. Invoke it later; do not rebuild it here.
4. **Does Workframe already do it?** Workspace installation, credentials, sessions, users, rooms, files, and runtime profiles belong to Workframe/create-workframe. Attach later; do not build a second platform.
5. **Can the first slice be smaller?** Yes: detect, ask for purpose, optionally classify a provisional form, and return a reviewable zero-mutation plan.

## MVP

```text
workframe status                    existing, unchanged
workframe start                     new thin dispatch
  -> reuse status JSON
  -> ask what the user wants to accomplish, for whom, and what success means
  -> optionally ask whether organization, business, project, or none yet should carry it
  -> name the best available inference candidate
  -> state that authorization is still required
  -> return the next question
  -> inspect nothing
  -> write nothing
```

Non-interactive form:

```bash
workframe start --json \
  --purpose="Build a durable operating context for my work." \
  --forms=business,project
```

## Explicitly deferred

- machine-wide or home-directory scanning;
- reading file contents;
- provider calls during formation;
- importing or copying credentials;
- a Workframe-hosted OpenRouter relay;
- custom ontology or knowledge compilers;
- automatic repository moves or copies;
- embeddings, graph databases, GraphRAG, or vector search;
- multi-user organization setup;
- agent-team generation;
- per-project Rail creation;
- Workframe installation or deployment;
- background maintenance loops;
- a general plugin or adapter framework.

These may become later independently testable features. None is foundational to the first slice.

## Minimum architecture

- `workframe-cli.js`: dispatch `start`; delegate every existing command unchanged.
- `origin-start.js`: capture purpose, parse bounded provisional forms, read existing status JSON, select a candidate, and print a plan.
- one assert-based test file.
- no new dependency.
- no network call.
- no write path.

## Deletion list from the original implementation concept

- Delete the proposed custom discovery engine; reuse status.
- Delete the proposed ontology compiler; use Architectonic.
- Delete the proposed workspace deployer; use create-workframe/Workframe.
- Delete the proposed credential importer; use existing vault/provider connection surfaces.
- Delete the proposed universal state machine for the first slice; a plain plan object is sufficient.
- Delete hosted fallback inference from the MVP.
- Delete automatic full-PC scanning from the MVP.
- Delete the assumption that every project needs a Rail; add Rail only when work crosses sessions, actors, dependencies, review, or approval.
- Delete the category mistake that organization, business, and project are purposes. They are only provisional forms that may carry a prior purpose.

## Upgrade path

The next feature may add **progressive path authorization and metadata-only inventory**. It must not be started until this slice proves:

- existing commands still behave identically;
- purpose capture and provisional-form parsing work in interactive and JSON modes;
- output states exactly what was and was not inspected;
- output contains no secrets;
- no filesystem mutation occurs;
- a nontechnical user can understand the result.
