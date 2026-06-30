// Profile resolution: lane → specialist role mapping.
export { SPECIALIST_ROLES } from "./types"

export const DEFAULT_LANE_MAP: Record<string, string> = {
  strategy: "visionary",
  architecture: "architect",
  planning: "architect",
  docs: "docs",
  implementation: "dev",
  test: "dev",
  research: "research",
  evidence: "research",
  ux: "designer",
  visual: "designer",
}

export const NATIVE_PROFILE_ID = "workframe-agent"

export function resolveLaneRoute(laneOrIntent: string): string {
  const lower = laneOrIntent.toLowerCase()
  for (const [keyword, role] of Object.entries(DEFAULT_LANE_MAP)) {
    if (lower.includes(keyword)) return role
  }
  return NATIVE_PROFILE_ID
}

export function isSpecialistRole(role: string): boolean {
  return role in SPECIALIST_ROLES
}
