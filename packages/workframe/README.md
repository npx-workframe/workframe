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
| `doctor` | Validate native-first layout, 4-service compose topology, manifest, and Docker runtime |
| `setup` | Print onboarding steps from `Workframe/SETUP.md` |

`doctor` is bootstrap-aware:

- before Hermes setup, it validates scaffold/layout and skips runtime-only checks
- after Hermes setup, it can validate compose/runtime expectations too

Planned: `up`, `down`, `profiles list`, `add-agent`.
