import type { Theme } from '@/lib/theme'

export type CanvasTexture = 'dots' | 'moleskine'

/** Theme → full-viewport texture layer, or null when atmosphere only. */
export function getThemeCanvasTexture(theme: Theme): CanvasTexture | null {
  if (theme === 'strato-dark') return 'dots'
  return null
}
