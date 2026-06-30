# workframe

Lifecycle CLI for existing Workframe projects.

## Usage

From inside a generated project:

```bash
npx workframe doctor
npx workframe setup
```

## Commands

| Command | Purpose |
|---------|---------|
| `doctor` | Validate project layout, compose file, manifest, Docker runtime, and native bootstrap |
| `setup` | Open Hermes setup flow for credentials |

`doctor` is bootstrap-aware:

- before Hermes setup, it validates scaffold/layout and skips runtime-only checks
- after Hermes setup, it can validate compose/runtime expectations too

Planned: `up`, `down`, `profiles list`, `add-agent`.
