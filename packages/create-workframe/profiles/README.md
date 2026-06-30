# Profile templates (package source)

Install-time packs reference a **project-agent** slot. At scaffold time it becomes `{slugify(projectName)}-agent` (e.g. `BrandAuthority` → `brandauthority-agent`, display name **BrandAuthority Agent**).

## Layout

- Native concierge SOUL template: `workframe-agent/SOUL.md` (rendered into the project-specific slug)
- Specialists: `visionary/`, `architect/`, `docs/`, `dev/`, `research/`, `designer/`

## Packs

- **core** — native project agent + docs + dev
- **product** — native + docs + dev + visionary + research + designer
- **engineering** — native + docs + dev + architect + research
- **vanilla** / **full** — native + all specialists
