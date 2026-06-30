# Workframe Routing Guide

Routing owner
- concierge (`{projectName} Agent`) owns routing decisions.

Default lanes
- strategy -> visionary
- architecture/planning -> architect
- docs hygiene -> docs
- implementation/test -> dev
- evidence/context -> research
- UX/visual -> designer

Routing rules
- parallelize independent lanes
- use dependencies only when required
- keep each lane role-pure
- persist final outcomes in files

Dynamic library rule
- if a request repeatedly falls outside current roles,
  concierge proposes a new specialist profile.

Routing model notes:

- the native project agent owns Discord / Telegram messaging surfaces
- specialist profile runtimes are started as API-only gateways inside the same Hermes container
- UI lanes bind sessions by `profile + source_id + client_id`
- session titles are lane-local and may be auto-suffixed for uniqueness
