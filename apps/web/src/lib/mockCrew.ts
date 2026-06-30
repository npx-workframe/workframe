export {
  buildMockCrew,
  crewInitials,
  findAgentByProfile,
  workframeAgentFromHermes,
  type HermesProfile,
  type WorkframeAgent,
} from '@/lib/hermesProfile'

import { buildMockCrew } from '@/lib/hermesProfile'

/** @deprecated Prefer `buildMockCrew(projectName)` for gateway-compatible crew rows. */
export const MOCK_CREW = buildMockCrew(
  import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe',
)
