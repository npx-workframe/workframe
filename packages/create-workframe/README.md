# create-workframe

Published on npm as **create-workframe**.

```bash
npx create-workframe@0.1.20 MyProject
```

Scaffolds an isolated Workframe + Hermes project on Windows, macOS, and Linux.

## Generated layout

```text
MyProject/
├── Agents/
├── Files/
├── scripts/              bootstrap, lifecycle, workframe.mjs CLI
├── docker-compose.yml
├── workframe-api/
├── workframe-ui/
├── workframe-supervisor/
└── workframe-manifest.json
```

## Project CLI

From the generated project root:

```bash
node scripts/workframe.mjs doctor
node scripts/workframe.mjs setup
```

## Source

[github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe)

Documentation: [docs/README.md](https://github.com/npx-workframe/workframe/blob/main/docs/README.md)

Apache-2.0 — see `LICENSE`, `NOTICE`, `SECURITY.md`.
