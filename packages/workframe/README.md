# workframe

The adaptive local entrypoint for Workframe and Architectonic bootstrap.

```bash
npx workframe@0.4.1
```

Version **0.4.1** adds real gated apply: `npx architectonic init`, organization writes, optional `create-workframe`, KB mirrored to `Files/organization`.

## Commands

```bash
npx workframe status [--json] [--no-test]
npx workframe begin [--json] [--human=...] [--entity=...] ...
npx workframe capabilities [--json]
npx workframe verify [--json] [--select="use codex"]
npx workframe draft [--json] ...
npx workframe plan [--json] [--target=path] ...
npx workframe apply --simulate [--json] [--approval="approve plan ..."]
npx workframe help
npx workframe version
```

### Flow

1. `begin` — memory-only Socratic mirror (no network, no writes)
2. `capabilities` — truthful runtime/provider candidates (no auto-pick)
3. `verify` — explicit path + separate consent + cancellable call
4. `draft` — constitutional in-memory draft
5. `plan` — dry-run Architectonic file plan + deployment recommendation
6. `apply --simulate` — approval gate simulation (real mutations disabled)

## Privacy and authority

- Discovery runs locally.
- Credential values are never printed.
- `begin`, `draft`, `plan`, and `apply` perform no network calls.
- No provider call occurs without explicit user approval on `verify`.
- This CLI does not install Hermes, Workframe, or Architectonic by itself.

## Full Workframe cell

```bash
npx create-workframe@0.1.38 MyProject
```

`workframe` inspects and interviews locally; `create-workframe` installs the product cell when a deployment plan says you need one.
