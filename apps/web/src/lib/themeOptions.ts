import type { LucideIcon } from 'lucide-react'
import { Compass, Layers, Monitor, Moon, Square, Sun } from 'lucide-react'

import type { Theme } from '@/lib/theme'

export type ThemeOption = {
  value: Theme
  label: string
  icon: LucideIcon
}

export const THEME_OPTIONS: ThemeOption[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'mono-light', label: 'Mono Light', icon: Monitor },
  { value: 'mono-dark', label: 'Mono Dark', icon: Monitor },
  { value: 'neo', label: 'Neo', icon: Layers },
  { value: 'brutal', label: 'Brutal', icon: Square },
  { value: 'architectonic', label: 'Architectonic', icon: Compass },
]
