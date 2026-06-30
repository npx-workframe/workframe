# Workframe Overview

Workframe is a usability + bootstrap layer on top of Hermes.

What it is:
- A reusable project starter for semi-autonomous agent collaboration.
- A way to operate where teams already talk (Telegram/Discord) while running durable work through Hermes Kanban.

What it is not:
- Not a Hermes fork.
- Not a custom orchestration engine replacing Hermes internals.

Ontology:
1) Concierge Agent: project-native coordinator (`{projectName} Agent`).
2) Specialist Library: modular, purpose-built agents (Visionary/Architect/Docs/Dev/Research/Designer + optional niche agents).
3) Context Planes:
   - Chat: human interaction and intent capture.
   - Session/Kanban: execution state and handoff continuity.
   - Files: canonical project truth.
4) Curation Principle: only load tools/skills that each role repeatedly needs.
