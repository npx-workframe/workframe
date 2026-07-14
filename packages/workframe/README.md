# workframe

The adaptive local entrypoint for Workframe.

```bash
npx workframe status
npx workframe begin
```

`status` performs read-only local discovery. It reports installed runtimes and the names—not the values—of configured provider credentials. It does not make an inference call.

`begin` offers only inference paths that can be represented truthfully. Account-backed CLI sessions and API-key-backed provider paths are separate candidates. When more than one candidate exists, the CLI requires a definite natural-language selection or explicit delegation; questions, hedges, and mixed choices remain unresolved.

Before verification, Workframe discloses the exact payer, credential source, and invocation path. One minimal verification call occurs only after separate explicit consent. Ctrl+C cancels an in-flight HTTP request or CLI child process. Runtime children receive a minimal inference environment without Docker, SSH, unrelated credentials, or other ambient authority handles.

After a successful verification, `begin` asks for a preferred name and one stated objective, then prints a deterministic first mirror. That mirror exists in memory only.

## Commands

```bash
npx workframe
npx workframe status
npx workframe status --json
npx workframe begin
npx workframe help
npx workframe version
```

## Privacy and authority

- Discovery runs locally and performs no inference.
- Credential values are never printed or persisted.
- Workframe does not search shell history or crawl arbitrary `.env` files.
- No provider call occurs without explicit approval of one exact path.
- Account-backed CLI paths do not receive provider API keys.
- Direct provider paths receive only the selected credential.
- Ctrl+C cancels pending verification and prevents the Socratic session from continuing.
- This slice writes no files and does not install, adopt, overwrite, or deploy anything.
- No Workframe-hosted or implicit cloud fallback is used.

The existing `create-workframe` package is outside this package and remains unchanged.
