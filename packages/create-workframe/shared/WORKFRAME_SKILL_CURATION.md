# Workframe Skill and Tool Curation

Purpose
- enforce lean specialization and avoid context bloat.

Skill matrix (recommended baseline)

| Profile | Mandatory (recommended) | Optional (recommended) | Avoid |
|---|---|---|---|
| {nativeProfileSlug} (project agent) | kanban-orchestrator | writing-plans, plan | domain-heavy implementation skills |
| visionary | writing-plans | arxiv, blogwatcher | low-level debugging stacks |
| architect | writing-plans | systematic-debugging, github-code-review | generic creative bundles |
| docs | humanizer | hermes-agent-skill-authoring | infra-heavy ops bundles |
| dev | test-driven-development, systematic-debugging | python-debugpy, requesting-code-review | broad strategy skills |
| research | arxiv | llm-wiki, blogwatcher | unrelated creative generators |
| designer | sketch | popular-web-designs, architecture-diagram | deep backend/debug toolchains |

Tool curation rules
1) Give each profile only tools it uses weekly.
2) Shared essentials should be small.
3) Add a skill only after repeated need.
4) Remove stale skills quarterly.

Install-time selection
- default to the `native` starter pack unless a larger reference pack is explicitly requested
- reference packs remain available (`core` / `product` / `engineering` / `full`)
- concierge can request profile add/remove later with owner approval.
