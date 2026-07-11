import type { Theme } from '@/lib/theme'

export type CanvasTexture = 'dots' | 'moleskine'

/** Theme → full-viewport texture layer, or null when atmosphere only.
 *  Neo relief themes: no texture (flat solid --wf-bg). Strato-dark: dots. */
export function getThemeCanvasTexture(theme: Theme): CanvasTexture | null {
  if (theme === 'strato-dark') return 'dots'
  return null
}
