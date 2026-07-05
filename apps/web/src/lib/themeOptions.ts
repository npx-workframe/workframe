import type { LucideIcon } from 'lucide-react'
import { Layers, Moon } from 'lucide-react'

import type { Theme } from '@/lib/theme'

export type ThemeOption = {
  value: Theme
  label: string
  icon: LucideIcon
}

export const THEME_OPTIONS: ThemeOption[] = [
  { value: 'neo', label: 'Neo', icon: Layers },
  { value: 'dark', label: 'Dark', icon: Moon },
]
