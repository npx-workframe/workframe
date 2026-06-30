# Workframe Chat Permission Model

Purpose: keep chat collaboration simple, safe, and aligned with Workframe ontology.

- Concierge agent is primary chat-facing interface.
- Specialists are invoked through routing, not random direct control by default.
- Platform permissions (Telegram/Discord roles/channels/threads) are the first trust gate.

Trust model:
- Owner/admin = highest-trust operator.
- Team members = permitted by platform-level access policy.

Risk model:
- default allowed: docs + Kanban + status work
- explicit approval required: high-impact external actions and credential changes

Truth model:
- chat = intent and coordination
- Kanban = execution state
- files = canonical project truth
