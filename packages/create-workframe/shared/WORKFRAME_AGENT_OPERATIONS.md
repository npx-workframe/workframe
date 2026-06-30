# Workframe Agent Operations

Goal
- keep the agent library dynamic but controlled.

Concierge responsibilities
- detect recurring specialist needs
- propose profile add/remove/swap
- route work through existing profiles until approved change lands
- spawn specialists only when a real role gap exists

Profile operations policy
- Add profile: when repeated tasks do not fit existing specialists.
- Remove profile: when low usage and overlapping role.
- Replace profile: when role remains but mission changes.

Approval
- owner/admin approves profile topology changes in team environments.

Preferred implementation path
1) Update runtime profile SOUL under `Agents/profiles/`.
2) Update bootstrap seeds under `scripts/seed/profiles/` when templates change.
3) Spawn or update the runtime profile set through lifecycle/botfather flows.
4) Announce changed routing behavior in docs and chat status.

Default topology policy
- Start native-only.
- Treat specialist packs as reference presets, not mandatory first boot state.
- Keep the installed crew as small as possible until real demand appears.
