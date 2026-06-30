# Workframe Agent Library

Model
- Main project agent (**{nativeAgentName}**) is concierge/orchestrator.
- Specialists are modular workers that can be installed/imported/removed.

Canonical behavior location
- Runtime: `Agents/profiles/{nativeProfileSlug}/SOUL.md`
- Bootstrap seed: `scripts/seed/profiles/{nativeProfileSlug}/SOUL.md`

Default specialist catalog
- visionary
- architect
- docs
- dev
- research
- designer

Install-time starter packs
- Recorded in `workframe-manifest.json` (`pack`, `profiles`, `native_agent`)
- Default scaffold pack is `native` (native agent only)
- Reference packs can still be chosen explicitly
- See `docs/SETUP.md` for the pack chosen at install

Extension pattern
- Add niche specialists only when recurring demand exists.
- Preferred path: spawn specialists on demand through botfather/lifecycle flows instead of preinstalling the whole crew.

Curation rule
- Keep role-specific skill/tool bundles lean.
- Avoid cloning massive identical bundles across all agents.
