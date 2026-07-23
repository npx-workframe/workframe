import { getThemeDefinition, type Theme } from '@/lib/theme'

export type CanvasTexture = Exclude<ReturnType<typeof getThemeDefinition>['texture'], 'none'>

export function getThemeCanvasTexture(theme: Theme): CanvasTexture | null {
  const texture = getThemeDefinition(theme).texture
  return texture === 'none' ? null : texture
}
