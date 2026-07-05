import { apiGet, apiPatch, apiPost } from '@/lib/apiClient'

export type HermesSkillRow = {
  name: string
  description: string
  category: string | null
  enabled: boolean
}

export type HermesSlashCommand = {
  name: string
  aliases?: string[]
  description: string
  category: string
  args_hint?: string
  dispatch?: string
  wired?: boolean
}

export type SlashDispatchResult = {
  ok: boolean
  dispatched?: 'client' | 'bff' | 'gateway' | 'noop'
  command?: string
  args?: string
  handler?: string
  message?: string
  error?: string
  suggestion?: string
  line?: string
}

export type HermesModelRow = {
  provider: string
  model: string
  label: string
  description: string
}

export type FallbackEntry = {
  provider: string
  model: string
  base_url?: string
}

export type HermesModelsResponse = {
  ok: boolean
  profile: string
  /** Primary model id (e.g. "openrouter/owl-alpha"). */
  primary: string
  /** Active provider key (e.g. "openrouter"). */
  provider: string
  /** Base URL the active provider is configured with. */
  base_url: string
  /** Resolved fallback chain — ordered, what Hermes tries after the
   *  primary fails. Sourced from the profile's config.yaml. */
  fallback_chain: FallbackEntry[]
  /** Curated suggestions for the active provider. The picker treats
   *  this as a hint list, not a hardcoded menu — users can also
   *  type any `provider/model` id. */
  suggestions: HermesModelRow[]
  /** The canonical defaults, surfaced for "reset to default" actions. */
  default_primary: string
  default_fallback_chain: FallbackEntry[]
  connected_providers?: string[]
  has_llm_provider?: boolean
  stack_llm_available?: boolean
  /** Billing provider for the active model (e.g. openrouter), not Hermes config provider (custom). */
  billing_provider?: string
  selection_only?: boolean
}

type SkillsResponse = {
  skills: HermesSkillRow[]
}

type CommandsResponse = {
  ok: boolean
  categories?: Array<{ name: string; commands: Array<[string, string]> }>
  entries?: HermesSlashCommand[]
}

export async function fetchHermesSkills(): Promise<HermesSkillRow[]> {
  const data = await apiGet<SkillsResponse>('/api/hermes/skills')
  return data.skills ?? []
}

/** Single HTTP hop. The BFF holds the static catalog; no WS round-trip. */
export async function fetchHermesCommands(): Promise<HermesSlashCommand[]> {
  const data = await apiGet<CommandsResponse>('/api/hermes/commands')
  return data.entries ?? []
}

/** Resolve and dispatch a slash command line. The BFF returns a hint;
 *  the UI runs the hint. Client/bff dispatches never call the gateway. */
export async function execHermesCommand(line: string): Promise<SlashDispatchResult> {
  return apiPost<SlashDispatchResult>('/api/hermes/commands/exec', { line })
}

export async function fetchHermesModels(
  profile?: string,
  workspaceId?: string,
  opts?: { selectionOnly?: boolean },
): Promise<HermesModelsResponse> {
  const params = new URLSearchParams()
  if (profile?.trim()) params.set('profile', profile.trim())
  if (workspaceId?.trim()) params.set('workspace_id', workspaceId.trim())
  if (opts?.selectionOnly) params.set('selection_only', '1')
  const query = params.toString() ? `?${params.toString()}` : ''
  return apiGet<HermesModelsResponse>(`/api/hermes/models${query}`)
}

export async function setHermesModel(
  model: string,
  profile?: string,
  workspaceId?: string,
  opts?: { selectionOnly?: boolean },
): Promise<{ ok: boolean; model?: string; error?: string }> {
  return apiPost('/api/hermes/model', {
    model,
    profile: profile ?? '',
    workspace_id: workspaceId ?? '',
    selection_only: Boolean(opts?.selectionOnly),
  })
}

export async function setHermesFallbackChain(
  chain: Array<{ provider: string; model: string }>,
  profile?: string,
  opts?: { selectionOnly?: boolean },
): Promise<{ ok: boolean; fallback_chain?: FallbackEntry[]; error?: string }> {
  return apiPost('/api/hermes/fallback-chain', {
    chain,
    profile: profile ?? '',
    selection_only: Boolean(opts?.selectionOnly),
  })
}

export type HermesUsageSession = {
  id: string
  title: string
  model: string
  message_count: number
  tool_call_count: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  started_at: string | null
  ended_at: string | null
}

export type HermesUsageResponse = {
  ok: boolean
  profile: string
  session: HermesUsageSession | null
  error?: string
}

export async function fetchHermesUsage(): Promise<HermesUsageResponse> {
  return apiGet<HermesUsageResponse>('/api/hermes/usage')
}

export type HermesGatewayExecResponse = {
  ok: boolean
  profile: string
  command: string
  rc: number
  output: string
  error?: string
}

export async function execHermesGateway(line: string, profile?: string): Promise<HermesGatewayExecResponse> {
  return apiPost<HermesGatewayExecResponse>('/api/hermes/gateway/exec', { line, profile: profile ?? '' })
}

export type HermesProfileResponse = {
  ok: boolean
  profile: string
  description: string
  gateway_running: boolean
  session: { id: string; title: string; message_count: number; model: string } | null
  error?: string
}

export async function fetchHermesProfile(): Promise<HermesProfileResponse> {
  return apiGet<HermesProfileResponse>('/api/hermes/profile')
}

export type HermesProfileDetailResponse = {
  ok: boolean
  profile: string
  display_name: string
  role: string
  tagline: string
  description: string
  soul: string
  soul_exists: boolean
  gateway_running: boolean
  gateway_state: string
  model: string
  provider: string
  is_native?: boolean
  avatar_id?: string
  avatar_url?: string
  error?: string
}

export async function fetchHermesProfileDetail(profile: string): Promise<HermesProfileDetailResponse> {
  return apiGet<HermesProfileDetailResponse>(`/api/hermes/profiles/${encodeURIComponent(profile)}`)
}

export async function updateHermesProfile(
  profile: string,
  patch: Partial<
    Pick<HermesProfileDetailResponse, 'display_name' | 'role' | 'tagline' | 'description' | 'avatar_url' | 'avatar_id'>
  >,
): Promise<{ ok: boolean; profile?: string; error?: string }> {
  return apiPatch(`/api/hermes/profiles/${encodeURIComponent(profile)}`, patch)
}

export async function fetchProfileSoul(profile: string): Promise<{ ok: boolean; profile: string; soul: string }> {
  return apiGet(`/api/hermes/profiles/${encodeURIComponent(profile)}/soul`)
}

export async function saveProfileSoul(
  profile: string,
  soul: string,
): Promise<{ ok: boolean; profile: string; bytes?: number; error?: string }> {
  return apiPost(`/api/hermes/profiles/${encodeURIComponent(profile)}/soul`, { soul })
}

export type ProfileGatewayStatusResponse = {
  ok: boolean
  profile: string
  action?: string
  state?: string
  api_port?: number
  details?: { state?: string; ok?: boolean }
  error?: string
}

export async function fetchProfileGatewayStatus(profile: string): Promise<ProfileGatewayStatusResponse> {
  return apiGet<ProfileGatewayStatusResponse>(
    `/api/hermes/profiles/status?profile=${encodeURIComponent(profile)}`,
  )
}

export async function startProfileGateway(profile: string): Promise<ProfileGatewayStatusResponse> {
  return apiPost<ProfileGatewayStatusResponse>('/api/hermes/profiles/start', { profile })
}

export async function stopProfileGateway(profile: string): Promise<ProfileGatewayStatusResponse> {
  return apiPost<ProfileGatewayStatusResponse>('/api/hermes/profiles/stop', { profile })
}

export type HermesDebugResponse = {
  ok: boolean
  profile: string
  python_version: string
  platform: string
  session_count: number
  message_count: number
  error?: string
}

export async function fetchHermesDebug(): Promise<HermesDebugResponse> {
  return apiGet<HermesDebugResponse>('/api/hermes/debug')
}

export type HermesInsightsResponse = {
  ok: boolean
  profile: string
  daily: Array<{ day: string; input_tokens: number; output_tokens: number; sessions: number }>
  models: Array<{ model: string; sessions: number; input_tokens: number }>
  error?: string
}

export async function fetchHermesInsights(): Promise<HermesInsightsResponse> {
  return apiGet<HermesInsightsResponse>('/api/hermes/insights')
}

export type HermesGquotaResponse = {
  ok: boolean
  profile: string
  configured: boolean
  message: string
  error?: string
}

export async function fetchHermesGquota(): Promise<HermesGquotaResponse> {
  return apiGet<HermesGquotaResponse>('/api/hermes/gquota')
}

export async function apiStopRun(profile: string): Promise<{ ok: boolean; error?: string }> {
  return apiPost<{ ok: boolean; error?: string }>('/api/chat/stop', { profile })
}

export async function apiSteerRun(profile: string, text: string): Promise<{ ok: boolean; error?: string }> {
  return apiPost<{ ok: boolean; error?: string }>('/api/chat/steer', { profile, text })
}
