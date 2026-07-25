import type { LucideIcon } from 'lucide-react'
import { BookOpen, Layers, Moon, Newspaper, Notebook, Palette, Ruler, Sparkles, Square, Sun } from 'lucide-react'

import { THEME_DEFINITIONS, type Theme } from '@/lib/theme'

/** Hidden from header switcher + settings appearance grid; themes stay valid if already selected. */
const HIDDEN_THEME_PICKER_IDS = new Set<Theme>([
  'mono',
  'neo-color',
  'minimal-color',
  'leather-book',
])

export type ThemeOption = {
  value: Theme
  label: string
  family: string
  icon: LucideIcon
  style: 'lines' | 'shadows' | 'glass'
  texture: string
  preview: {
    canvas: string
    surface: string
    ink: string
    accent: string
  }
}

const FAMILY_ICON: Record<string, LucideIcon> = {
  lines: Square,
  neo: Layers,
  brutalist: Ruler,
  glass: Sparkles,
  special: Palette,
}

const THEME_ICON: Partial<Record<Theme, LucideIcon>> = {
  'minimal-light': Sun,
  'minimal-dark': Moon,
  'neo-light': Sun,
  'neo-dark': Moon,
  'liquid-glass-light': Sun,
  'liquid-glass-dark': Moon,
  'frosted-glass-light': Sun,
  'frosted-glass-dark': Moon,
  'leather-book': BookOpen,
  newspaper: Newspaper,
  notebook: Notebook,
}

export const THEME_OPTIONS: ThemeOption[] = THEME_DEFINITIONS.filter(
  (definition) => !HIDDEN_THEME_PICKER_IDS.has(definition.id),
).map((definition) => ({
  value: definition.id,
  label: definition.label,
  family: definition.family,
  icon: THEME_ICON[definition.id] ?? FAMILY_ICON[definition.family] ?? Palette,
  style: definition.style,
  texture: definition.texture,
  preview: definition.preview,
}))

export const THEME_FAMILY_LABELS: Record<string, string> = {
  lines: 'Lines',
  neo: 'Neo',
  brutalist: 'Brutalist',
  glass: 'Glass',
  special: 'Specialized',
}

export const THEME_OPTION_GROUPS = [...new Set(THEME_OPTIONS.map((option) => option.family))]
  .map((family) => ({
    family,
    label: THEME_FAMILY_LABELS[family] ?? family,
    options: THEME_OPTIONS.filter((option) => option.family === family),
  }))
  .filter((group) => group.options.length > 0)
