# workframe

The adaptive local entrypoint for Workframe.

```bash
npx workframe
```

Version `0.2.0` is intentionally read-only. It discovers installed agent runtimes and model-provider configuration, then presents a local status console.

When a supported inference path is already available, Workframe offers one minimal verification call. The user may answer naturally rather than entering a fixed `y/N` token. The call runs only after explicit approval and may use the user's existing paid account or API key.

If no supported inference path is available, Workframe stops without installing or changing anything.

## Commands

```bash
npx workframe
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
- No provider call occurs without explicit user approval.
- This release does not install Hermes, Workframe, agents, or packages.
- This release does not use a Workframe-hosted fallback API.

The existing `create-workframe` package remains unchanged and continues to scaffold complete Workframe installations.
