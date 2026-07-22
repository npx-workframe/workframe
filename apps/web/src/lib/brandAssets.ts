import anthropic from '@/assets/brands/anthropic.svg?url'
import brave from '@/assets/brands/brave.svg?url'
import cursor from '@/assets/brands/cursor.svg?url'
import discord from '@/assets/brands/discord.svg?url'
import gemini from '@/assets/brands/gemini.svg?url'
import github from '@/assets/brands/github.svg?url'
import google from '@/assets/brands/google.svg?url'
import grok from '@/assets/brands/grok.svg?url'
import netlify from '@/assets/brands/netlify.svg?url'
import nvidia from '@/assets/brands/nvidia.svg?url'
import openai from '@/assets/brands/openai.svg?url'
import openrouter from '@/assets/brands/openrouter.svg?url'
import perplexity from '@/assets/brands/perplexity.svg?url'
import stripe from '@/assets/brands/stripe.svg?url'
import telegram from '@/assets/brands/telegram.svg?url'
import vercel from '@/assets/brands/vercel.svg?url'
import workframe from '@/assets/brands/workframe.svg?url'
import workframeColor from '@/assets/branding/workframe-color.svg?url'

/** Integration and sign-in marks — source: `src/assets/brands/`. */
export const BRAND_ICON = {
  workframe,
  workframeColor,
  google,
  github,
  discord,
  telegram,
  stripe,
  netlify,
  vercel,
  anthropic,
  cursor,
  openai,
  openrouter,
  perplexity,
  nvidia,
  gemini,
  grok,
  brave,
} as const

export type BrandIconId = keyof typeof BRAND_ICON

export type ProviderBrandId =
  | 'anthropic'
  | 'openai'
  | 'openrouter'
  | 'cursor'
  | 'perplexity'
  | 'nous'
  | 'github'
  | 'codex'
  | 'google'
  | 'gemini'
  | 'deepseek'
  | 'brave'
  | 'grok'
  | 'nvidia'
  | 'stripe'

const PROVIDER_ICON_BY_ID: Partial<Record<ProviderBrandId, string>> = {
  anthropic: BRAND_ICON.anthropic,
  openai: BRAND_ICON.openai,
  openrouter: BRAND_ICON.openrouter,
  cursor: BRAND_ICON.cursor,
  perplexity: BRAND_ICON.perplexity,
  github: BRAND_ICON.github,
  codex: BRAND_ICON.openai,
  google: BRAND_ICON.google,
  gemini: BRAND_ICON.gemini,
  brave: BRAND_ICON.brave,
  grok: BRAND_ICON.grok,
  nvidia: BRAND_ICON.nvidia,
  stripe: BRAND_ICON.stripe,
}

export function providerIconForId(providerId: string): string | null {
  const key = providerId.trim().toLowerCase()
  return PROVIDER_ICON_BY_ID[key as ProviderBrandId] ?? null
}

/** Human label for billing provider ids (codex, openrouter) — not Hermes config ids (custom, openai-codex). */
export function billingProviderDisplayLabel(providerId: string): string {
  const key = providerId.trim().toLowerCase()
  if (!key || key === 'custom') return ''
  if (key === 'openrouter') return 'OpenRouter'
  if (key === 'openai') return 'OpenAI'
  if (key === 'anthropic') return 'Anthropic'
  if (key === 'google' || key === 'gemini') return 'Gemini'
  if (key === 'codex' || key === 'openai-codex' || key === 'openai_codex') return 'Codex'
  if (key === 'deepseek') return 'DeepSeek'
  if (key === 'nous') return 'Nous'
  return providerId
}
