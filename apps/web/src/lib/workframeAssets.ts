import { type ProviderBrandId } from '@/lib/brandAssets'
import { agentPresetUrl } from '@/lib/presetAssets'

export { DEFAULT_USER_AVATAR, DEFAULT_WORKSPACE_LOGO } from '@/lib/presetAssets'
export { providerIconForId, type ProviderBrandId as ProviderId } from '@/lib/brandAssets'

/** Hermes profile slug → specialist avatar (placeholders until gateway crew snapshot). */
export const AGENT_AVATAR_BY_SLUG: Record<string, string> = {
  visionary: agentPresetUrl('steve') ?? '',
  dev: agentPresetUrl('woz') ?? '',
  designer: agentPresetUrl('ada') ?? '',
  architect: agentPresetUrl('andy') ?? '',
  docs: agentPresetUrl('joni') ?? '',
  research: agentPresetUrl('nikola') ?? '',
  qa: agentPresetUrl('grace') ?? '',
  andy: agentPresetUrl('andy') ?? '',
}

export function agentAvatarForSlug(slug: string): string | null {
  const mapped = AGENT_AVATAR_BY_SLUG[slug.toLowerCase()]
  return mapped || null
}

export function inferProviderFromModelId(modelId: string): ProviderBrandId {
  const normalized = modelId.toLowerCase()
  if (normalized.startsWith('anthropic/')) return 'anthropic'
  if (normalized.startsWith('openai/')) return 'openai'
  if (normalized.startsWith('nous/')) return 'nous'
  if (normalized.includes('cursor')) return 'cursor'
  if (normalized.includes('perplexity')) return 'perplexity'
  return 'openrouter'
}
