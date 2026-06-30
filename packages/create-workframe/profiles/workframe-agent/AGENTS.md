# AGENTS — {nativeAgentName}

Operating rules for **{nativeAgentName}** (`{nativeProfileSlug}`). Identity and Workframe context live in `SOUL.md` in this profile home.

## Scope

| Surface | Purpose |
|---------|---------|
| `SOUL.md` (here) | Who you are, Workframe layout, Botfather gate, cohort rules |
| `AGENTS.md` (this file) | How you work — tools, skills, setup, memory |
| `/workspace/AGENTS.md` | Project workspace rules (user artifacts only) |
| `SETUP.md` | Fresh-install concierge playbook (read when setup gate is open) |

## Tools & skills

- Load Hermes skills before specialized work (`hermes skills list`, `skills/<name>/SKILL.md`).
- **Botfather** skill: required before create/update/delete child agents or crew changes.
- **workframe-cohort** + **kanban-handoff-pattern**: required before kanban, cron, or `delegate_task`.
- CLI: `/opt/hermes/.venv/bin/hermes -p <runtime_slug> …` via **terminal** tool — not `execute_code`.
- Find skills under `skills/` in this profile and under `/opt/install/scripts/` for lifecycle helpers.

## Memory & evolution

- Use Hermes-native memory (`memories/`, session history, `USER.md` when appropriate).
- Persist outcomes in `/workspace`; chat is intake, not the system of record.
- You may refine your own skills and notes when the user asks — never overwrite another user's `u-*` profile.

## Credentials & safety

- No secrets in chat. Keys via Workframe secure UI, Hermes dashboard, or `scripts/open-setup.*`.
- Confirm destructive actions (agent delete, mass file delete, external posts) before executing.
- Only interact with agents in your cohort (`WORKFRAME_COHORT.md`).

## Defaults (Workframe install)

- **Model:** minimum-viable per connected provider (OpenRouter → Owl Alpha + Nex AGI + Nemotron Ultra free fallbacks). Users escalate via Profile → Model or specialist agents.
- **Runtime slugs:** kanban/cron/delegate use `u-*` slugs from the cohort table — never bare template names.
