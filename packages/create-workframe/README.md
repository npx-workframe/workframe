# create-workframe

Published on npm as **create-workframe**.

```bash
npx create-workframe@0.1.59 MyProject
```

Scaffolds an isolated Workframe + Hermes project on Windows, macOS, and Linux.

## Generated layout

```text
MyProject/
â”œâ”€â”€ Agents/
â”œâ”€â”€ Files/
â”œâ”€â”€ scripts/              bootstrap, lifecycle, workframe.mjs CLI
â”œâ”€â”€ docker-compose.yml
â”œâ”€â”€ workframe-api/
â”œâ”€â”€ workframe-ui/
â”œâ”€â”€ workframe-supervisor/
â””â”€â”€ workframe-manifest.json
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

Apache-2.0 â€” see `LICENSE`, `NOTICE`, `SECURITY.md`.
