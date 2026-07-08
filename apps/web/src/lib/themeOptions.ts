import type { LucideIcon } from 'lucide-react'
import { Layers, Moon, Ruler } from 'lucide-react'

import type { Theme } from '@/lib/theme'

export type ThemeOption = {
  value: Theme
  label: string
  icon: LucideIcon
}

export const THEME_OPTIONS: ThemeOption[] = [
  { value: 'neo-light', label: 'Neo Light', icon: Layers },
  { value: 'neo-blue', label: 'Neo Blue', icon: Ruler },
  { value: 'strato-dark', label: 'Strato Dark', icon: Moon },
]
