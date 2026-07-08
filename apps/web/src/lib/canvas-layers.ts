import type { Theme } from '@/lib/theme'

export type CanvasTexture = 'dots' | 'moleskine'

/**
 * Canvas layer model (bottom → top):
 * 1. AtmosphereBg — solid --wf-bg, gradient, orbs, vignette overlay
 * 2. DotGrid | MoleskineGrid — repeating texture on full viewport
 *
 * Shell chrome is transparent (relief) so layer 2 shows through UI surfaces.
 */
export function getThemeCanvasTexture(theme: Theme): CanvasTexture {
  if (theme === 'blueprint') return 'moleskine'
  return 'dots'
}
