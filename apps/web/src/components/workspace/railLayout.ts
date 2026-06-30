export const RAIL_WIDTH = {
  expanded: 200,
  collapsed: 52,
} as const

export type RailLayout = keyof typeof RAIL_WIDTH
