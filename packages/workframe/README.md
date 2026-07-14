# workframe

The adaptive local entrypoint for Workframe.

```bash
npx workframe
```

Version `0.2.1` discovers installed agent runtimes and model-provider configuration without changing the host. When more than one supported inference path is available, Workframe asks which one to use in natural language, resolves one explicit choice, discloses the billing source, and requires separate explicit approval before one minimal verification call.

The `begin` command continues from a verified link into a memory-only Socratic handshake. It asks who is speaking and what they are trying to bring into existence, then reflects a bounded first draft with unresolved purpose, constraints, and success criteria. It does not yet invoke the model for the dialogue, write constitutional files, install Architectonic, or deploy Workframe.

## Commands

```bash
npx workframe
npx workframe begin
npx workframe status
npx workframe status --json
npx workframe status --no-test
npx workframe help
npx workframe version
```

## Privacy and authority

- Discovery runs locally.
- Credential values are never printed.
- Workframe does not search shell history or crawl arbitrary `.env` files.
- Runtime selection and provider consent are separate decisions.
- Negative language overrides positive words in mixed consent.
- No provider call occurs without explicit approval.
- The `begin` draft exists in memory only.
- No command in this release installs Hermes, Architectonic, Workframe, agents, or packages.
- No command in this release changes or adopts an existing setup.
- This release does not use a Workframe-hosted fallback API.

The existing `create-workframe` package remains unchanged and continues to scaffold complete Workframe installations.
