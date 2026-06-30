# Workframe Overview

Workframe is a usability and bootstrap layer on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent).

What it is:

- A reusable project starter for semi-autonomous agent collaboration
- A way to operate where teams already talk (Telegram/Discord) while running durable work through Hermes Kanban

What it is not:

- Not a Hermes fork
- Not a custom orchestration engine replacing Hermes internals

Ontology:

1. **Concierge agent** — project-native coordinator (`{projectName} Agent`)
2. **Specialist library** — modular role agents (visionary, architect, docs, dev, research, designer)
3. **Context planes** — chat (intent), Kanban/session (execution), files (canonical truth)
4. **Curation** — load only the tools and skills each role repeatedly needs

Full documentation: [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe/tree/main/docs/public)
