/** Central Workframe error parsing and user-facing copy. */

export type WorkframeNoticeTone = 'neutral' | 'info' | 'caution'

export type WorkframeNoticeAction =
  | { type: 'open_settings'; tab: 'providers' | 'model' | 'profile' | 'agents' | 'appearance' | 'connect' }
  | { type: 'external_link'; url: string; label?: string }
  | { type: 'retry' }

export type WorkframeNoticeInfo = {
  message: string
  hint?: string
  code?: string
  status?: number
  tone: WorkframeNoticeTone
  actionLabel?: string
  action?: WorkframeNoticeAction
  secondary_action_label?: string
  secondary_action?: WorkframeNoticeAction
}

export const AVATAR_MAX_FILE_BYTES = 256 * 1024
export const AVATAR_MAX_DATA_URL_CHARS = 380_000

const HTTP_COPY: Record<number, { message: string; hint?: string }> = {
  400: { message: 'Request could not be processed.', hint: 'Check the fields and try again.' },
  401: { message: 'Session expired or not signed in.', hint: 'Refresh the page and sign in again.' },
  403: { message: 'You do not have permission for this action.' },
  404: { message: 'That resource was not found.', hint: 'It may have been removed or renamed.' },
  409: { message: 'This conflicts with existing data.', hint: 'Refresh and try again.' },
  413: {
    message: 'Upload is too large for the server.',
    hint: 'Use a smaller file (avatars: under 256 KB; images: compress or resize first).',
  },
  415: { message: 'Unsupported request format.', hint: 'Try again from the latest UI build.' },
  429: { message: 'Too many requests.', hint: 'Wait a moment and try again.' },
  500: { message: 'Server error.', hint: 'Check API logs if this keeps happening.' },
  502: { message: 'Upstream service unavailable.', hint: 'Is the Workframe stack running?' },
  503: { message: 'Service temporarily unavailable.', hint: 'Retry in a few seconds.' },
}

const CODE_COPY: Record<string, { message: string; hint?: string; actionLabel?: string }> = {
  no_session: { message: 'You are not signed in.', hint: 'Sign in and try again.' },
  install_closed: {
    message: 'Install setup is already finished.',
    hint: 'Open the main app or finish user onboarding in Settings.',
  },
  oauth_start_failed: {
    message: 'Could not start provider sign-in inside the gateway.',
    hint: 'Retry in a moment. If it keeps failing, ask an admin to rebuild the workframe-supervisor container.',
  },
  raw_container_exec_disabled: {
    message: 'Provider sign-in is blocked on this secure stack.',
    hint: 'Rebuild workframe-api and workframe-supervisor from the latest release, then try again.',
  },
  device_oauth_start_failed: {
    message: 'Could not start device sign-in for this provider.',
    hint: 'Retry, or connect with an API key instead.',
  },
  invalid_device_oauth_provider: {
    message: 'This provider does not support device sign-in on this stack.',
    hint: 'Use an API key or a different connect method.',
  },
  email_required: {
    message: 'Email is required.',
    hint: 'Enter your email address before continuing.',
  },
  forbidden: {
    message: 'You do not have permission for this action.',
    hint: 'Sign in as the workspace admin, or finish the Admin step before saving Workframe settings.',
  },
  room_access_denied: { message: 'You cannot access this room.' },
  room_not_found: { message: 'Room not found.', hint: 'Refresh the room list or open another chat.' },
  room_not_agent_chat: { message: 'This room is not an agent chat.' },
  profile_not_installed: { message: 'Agent profile is not installed on this stack.' },
  unknown_profile: { message: 'Unknown agent profile.' },
  avatar_too_large: {
    message: 'Avatar image is too large.',
    hint: 'Use a square image under 256 KB (JPEG or PNG).',
  },
  provider_empty_reply: {
    message: 'The model provider returned no reply.',
    hint: 'Check your API key, credits, and model selection in Settings.',
    actionLabel: 'Choose model',
  },
  model_unavailable: {
    message: 'The selected model is not available on your provider right now.',
    hint: 'Pick a different model — free models on OpenRouter rotate often.',
    actionLabel: 'Choose model',
  },
  model_invalid_id: {
    message: 'That model ID is not valid for your provider.',
    hint: 'Open the model picker and select a listed model.',
    actionLabel: 'Choose model',
  },
  provider_invalid_key: {
    message: 'Your API key was rejected by the provider.',
    hint: 'Reset the key at the integration, then paste it again under Settings → Integrations.',
    actionLabel: 'Update API key',
  },
  provider_no_credits: {
    message: 'Your provider account has no credits remaining.',
    hint: 'Add credits at your provider billing page, then try again.',
    actionLabel: 'Add credits',
  },
  invalid_lease: {
    message: 'Your session credential expired before the model replied.',
    hint: 'Send the message again.',
    actionLabel: 'Try again',
  },
  concierge_add_keys: {
    message: 'Connect an LLM integration to enable chat.',
    hint: 'OpenRouter is the fastest path — paste your API key under Settings → Integrations.',
    actionLabel: 'Add API key',
  },
  concierge_change_model: {
    message: 'Choose which model this agent uses.',
    hint: 'Open the model picker and select a model your provider supports.',
    actionLabel: 'Choose model',
  },
  no_llm_provider_for_user: {
    message: 'No LLM integration is connected for your account.',
    hint: 'Add an OpenRouter or other LLM key under Settings → Integrations.',
    actionLabel: 'Connect integration',
  },
  unauthorized: { message: 'Authentication required.', hint: 'Sign in and try again.' },
  supervisor_unavailable: {
    message: 'Supervisor service is not running.',
    hint: 'On the server: cd infra/compose/workframe && docker compose up -d',
  },
  private_workspace: {
    message: 'This Workframe is private.',
    hint: 'Contact your Workframe admin for an invite link.',
  },
}

function humanizeCode(code: string): string {
  const trimmed = code.trim()
  if (!trimmed) return 'An unexpected error occurred.'
  if (CODE_COPY[trimmed]) return CODE_COPY[trimmed].message
  if (/^[a-z][a-z0-9_]*$/.test(trimmed)) {
    return trimmed.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) + '.'
  }
  return trimmed
}

function hintForCode(code: string): string | undefined {
  return CODE_COPY[code.trim()]?.hint
}

const DEFAULT_ACTIONS: Record<string, WorkframeNoticeAction> = {
  no_llm_provider_for_user: { type: 'open_settings', tab: 'providers' },
  no_llm_provider: { type: 'open_settings', tab: 'providers' },
  provider_invalid_key: { type: 'open_settings', tab: 'providers' },
  provider_no_credits: { type: 'external_link', url: 'https://openrouter.ai/credits', label: 'Add credits' },
  model_unavailable: { type: 'open_settings', tab: 'model' },
  model_invalid_id: { type: 'open_settings', tab: 'model' },
  provider_rate_limited: { type: 'open_settings', tab: 'model' },
  provider_empty_reply: { type: 'open_settings', tab: 'model' },
  invalid_lease: { type: 'retry' },
  concierge_add_keys: { type: 'open_settings', tab: 'providers' },
  concierge_change_model: { type: 'open_settings', tab: 'model' },
  concierge_getting_started: { type: 'open_settings', tab: 'providers' },
  concierge_diagnose: { type: 'open_settings', tab: 'providers' },
}

function parseNoticeAction(raw: unknown): WorkframeNoticeAction | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const row = raw as Record<string, unknown>
  const type = String(row.type || '').trim()
  if (type === 'open_settings') {
    const tab = String(row.tab || 'providers').trim() as WorkframeNoticeAction & { type: 'open_settings' } extends never ? string : 'providers' | 'model' | 'profile' | 'agents' | 'appearance' | 'connect'
    if (tab === 'model') return { type: 'open_settings', tab: 'model' }
    if (tab === 'profile' || tab === 'agents' || tab === 'appearance') {
      return { type: 'open_settings', tab }
    }
    return { type: 'open_settings', tab: 'providers' }
  }
  if (type === 'external_link') {
    const url = String(row.url || '').trim()
    if (!url) return undefined
    return { type: 'external_link', url, label: String(row.label || '').trim() || undefined }
  }
  if (type === 'retry') return { type: 'retry' }
  return undefined
}

export function noticeFromStreamPayload(data: Record<string, unknown>): WorkframeNoticeInfo {
  const code = String(data.code || '').trim()
  const copy = code ? CODE_COPY[code] : undefined
  const message = String(data.message || data.text || data.error || copy?.message || '').trim()
  const hint = String(data.hint || copy?.hint || '').trim() || undefined
  const action = parseNoticeAction(data.action) || (code ? DEFAULT_ACTIONS[code] : undefined)
  const secondary_action = parseNoticeAction(data.secondary_action)
  return {
    tone: 'caution',
    code: code || undefined,
    message: message || 'An unexpected error occurred.',
    hint,
    actionLabel: String(data.action_label || copy?.actionLabel || '').trim() || undefined,
    action,
    secondary_action_label: String(data.secondary_action_label || '').trim() || undefined,
    secondary_action,
  }
}

function parseJsonBody(text: string): Record<string, unknown> | null {
  try {
    const data = JSON.parse(text) as unknown
    return typeof data === 'object' && data ? (data as Record<string, unknown>) : null
  } catch {
    return null
  }
}

function bodyMessage(data: Record<string, unknown> | null): string {
  if (!data) return ''
  for (const key of ['error', 'message', 'detail']) {
    const value = data[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function bodyCode(data: Record<string, unknown> | null): string | undefined {
  if (!data) return undefined
  const error = data.error
  if (typeof error === 'string' && error.trim()) return error.trim()
  return undefined
}

function bodyHint(data: Record<string, unknown> | null): string | undefined {
  if (!data) return undefined
  for (const key of ['hint', 'reason']) {
    const value = data[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return undefined
}

export function isProviderSetupError(message: string): boolean {
  return /no_llm_provider_for_user|no model provider is connected|api[_ ]?key|openrouter_api_key|provider key|model provider/i.test(
    message,
  )
}

function providerFailureNotice(raw: string): WorkframeNoticeInfo | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const info = formatWorkframeError(trimmed)
  if (info.code === 'no_llm_provider_for_user' || isProviderSetupError(info.message)) {
    return info
  }
  if (/invalid.*(api[_ ]?key|token)|authentication failed|incorrect api key|unauthorized|401|403/i.test(trimmed)) {
    return {
      tone: 'caution',
      message: 'Model provider rejected the request.',
      hint: 'Check your API key and the model selected in Settings.',
      actionLabel: 'Connect integration',
    }
  }
  if (/model.*(not found|does not exist|unknown)|invalid model/i.test(trimmed)) {
    return {
      tone: 'caution',
      message: 'The selected model is not available.',
      hint: 'Pick another model in Settings or confirm your provider account supports it.',
    }
  }
  return null
}

export function formatWorkframeError(err: unknown, context?: string): WorkframeNoticeInfo {
  const prefix = context?.trim() ? `${context.trim()}: ` : ''

  if (err && typeof err === 'object' && 'message' in err && 'tone' in err) {
    return err as WorkframeNoticeInfo
  }

  if (err instanceof Response) {
    return { ...formatHttpStatus(err.status), message: prefix + formatHttpStatus(err.status).message }
  }

  const raw = err instanceof Error ? err.message.trim() : String(err ?? '').trim()
  if (!raw || raw === 'Error' || raw === 'HTTP undefined') {
    return {
      tone: 'caution',
      message: prefix + (context ? 'An unexpected error occurred.' : 'An unexpected error occurred.'),
      hint: 'Check the browser network tab or API logs for details.',
    }
  }

  const httpMatch = raw.match(/^HTTP (\d{3})$/)
  if (httpMatch) {
    const info = formatHttpStatus(Number(httpMatch[1]))
    return { ...info, message: prefix + info.message }
  }

  const apiMatch = raw.match(/^(?:GET|POST|PATCH|PUT|DELETE) \S+ failed: (.+)$/i)
  const apiBody = apiMatch?.[1]?.trim() || raw
  const codeHint = hintForCode(apiBody)
  if (CODE_COPY[apiBody]) {
    const copy = CODE_COPY[apiBody]
    return {
      tone: 'caution',
      code: apiBody,
      message: prefix + copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
    }
  }

  if (/too large|entity too large|payload too large|413/i.test(apiBody)) {
    const info = formatHttpStatus(413)
    return { ...info, message: prefix + info.message }
  }

  if (/no llm provider|openrouter_api_key not set|provider configured|no_llm_provider_for_user/i.test(apiBody)) {
    const copy = CODE_COPY.no_llm_provider_for_user
    return {
      tone: 'caution',
      message: prefix + copy.message,
      hint: copy.hint,
      code: 'no_llm_provider_for_user',
      actionLabel: copy.actionLabel,
    }
  }

  if (/failed to fetch|networkerror|load failed/i.test(apiBody)) {
    return {
      tone: 'caution',
      message: prefix + 'Could not reach the Workframe API.',
      hint: 'Use http://127.0.0.1:18644 for dogfood, confirm Docker is up, or sign in again if the session expired.',
    }
  }

  return {
    tone: 'caution',
    message: prefix + (humanizeCode(apiBody) === apiBody ? apiBody : humanizeCode(apiBody)),
    hint: codeHint,
  }
}

export function formatHttpStatus(status: number): WorkframeNoticeInfo {
  const copy = HTTP_COPY[status]
  if (copy) {
    return { tone: 'caution', status, message: copy.message, hint: copy.hint, code: `http_${status}` }
  }
  return {
    tone: 'caution',
    status,
    message: `Request failed (HTTP ${status}).`,
    hint: 'Check the network response in devtools.',
    code: `http_${status}`,
  }
}

export async function parseApiErrorResponse(response: Response): Promise<WorkframeNoticeInfo> {
  const status = response.status
  let text = ''
  try {
    text = await response.text()
  } catch {
    text = ''
  }

  const data = text ? parseJsonBody(text) : null
  const code = bodyCode(data)
  const hint = bodyHint(data) || (code ? hintForCode(code) : undefined)
  let message = bodyMessage(data)

  if (!message && code && CODE_COPY[code]) {
    message = CODE_COPY[code].message
  }
  if (code === 'private_workspace' && typeof data?.message === 'string' && data.message.trim()) {
    message = data.message.trim()
  }
  if (!message && code) {
    message = humanizeCode(code)
  }
  if (!message && HTTP_COPY[status]) {
    message = HTTP_COPY[status].message
  }
  if (!message) {
    message = status ? `Request failed (HTTP ${status}).` : 'Request failed.'
  }

  return {
    tone: status >= 500 ? 'caution' : 'caution',
    status,
    code,
    message,
    hint: hint || HTTP_COPY[status]?.hint,
  }
}

export function noticeMessage(info: WorkframeNoticeInfo): string {
  return info.hint ? `${info.message} — ${info.hint}` : info.message
}

export function formatWorkframeErrorMessage(err: unknown, context?: string): string {
  return noticeMessage(formatWorkframeError(err, context))
}

export function streamErrorText(payload: Record<string, unknown>): string {
  if (payload.code || payload.action) {
    return noticeMessage(noticeFromStreamPayload(payload))
  }
  const raw = String(payload.text ?? payload.content ?? payload.message ?? payload.error ?? '').trim()
  if (raw) {
    const provider = providerFailureNotice(raw)
    if (provider) return noticeMessage(provider)
    return raw
  }
  const warning = String(payload.warning ?? '').trim()
  if (warning) {
    const provider = providerFailureNotice(warning)
    if (provider) return noticeMessage(provider)
    return warning
  }
  const status = String(payload.status ?? '').trim().toLowerCase()
  if (status === 'error') {
    return noticeMessage({
      tone: 'caution',
      message: 'The agent could not reach the model provider.',
      hint: 'Check API keys in Settings → Integrations and the model in Agent Settings.',
      actionLabel: 'Connect integration',
    })
  }
  if (status === 'interrupted') return 'The agent turn was interrupted.'
  return noticeMessage({
    tone: 'caution',
    message: 'The agent reported an error without details.',
    hint: 'Check integration keys, model selection, and gateway logs.',
  })
}

/** Shown when a chat stream ends with no assistant text. */
export function emptyAgentReplyText(options?: { streamError?: string; llmReady?: boolean }): string {
  const streamError = options?.streamError?.trim()
  if (streamError) return streamError
  if (options?.llmReady === false) {
    const copy = CODE_COPY.no_llm_provider_for_user
    return noticeMessage({
      tone: 'caution',
      code: 'no_llm_provider_for_user',
      message: copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
    })
  }
  return noticeMessage({
    tone: 'caution',
    message: 'The agent returned no reply.',
    hint: 'The model gateway may have rejected the request — try sending again. If it persists, check Settings → Integrations and the model in Agent Settings.',
    actionLabel: 'Connect integration',
  })
}

export function validateAvatarFile(file: File): WorkframeNoticeInfo | null {
  if (!file.type.startsWith('image/')) {
    return {
      tone: 'caution',
      message: 'Avatar must be an image file.',
      hint: 'Use JPEG, PNG, GIF, or WebP.',
      code: 'avatar_type',
    }
  }
  if (file.size > AVATAR_MAX_FILE_BYTES) {
    return {
      tone: 'caution',
      message: 'Avatar image is too large.',
      hint: `Choose a file under ${Math.round(AVATAR_MAX_FILE_BYTES / 1024)} KB.`,
      code: 'avatar_too_large',
    }
  }
  return null
}

// ponytail: self-check — fails fast if HTTP/status copy drifts
if (import.meta.env.DEV) {
  const sample = formatHttpStatus(413)
  if (!sample.message.includes('too large')) {
    console.warn('[workframeErrors] unexpected 413 copy', sample)
  }
}
