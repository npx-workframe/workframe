/** Central Workframe error parsing and user-facing copy. */
import errorPhrases from '@/data/errorPhrases.en.json'

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

type PhraseCopy = {
  message: string
  hint?: string
  actionLabel?: string
}

type ErrorPhrases = {
  fallback: PhraseCopy
  internal: PhraseCopy
  http: Record<string, PhraseCopy>
  codes: Record<string, PhraseCopy>
  patterns: Array<{ id: string; match: string; code: string }>
  contexts?: Record<string, PhraseCopy>
}

const PHRASES = errorPhrases as ErrorPhrases

export class WorkframeApiError extends Error {
  readonly notice: WorkframeNoticeInfo

  constructor(notice: WorkframeNoticeInfo, method?: string, path?: string) {
    const msg = notice.message?.trim() || PHRASES.fallback.message
    super(method && path ? `${method} ${path} failed: ${msg}` : msg)
    this.name = 'WorkframeApiError'
    this.notice = notice
  }
}

export const AVATAR_MAX_FILE_BYTES = 256 * 1024
export const AVATAR_MAX_DATA_URL_CHARS = 380_000

const HTTP_COPY: Record<number, PhraseCopy> = Object.fromEntries(
  Object.entries(PHRASES.http).map(([status, copy]) => [Number(status), copy]),
) as Record<number, PhraseCopy>

const CODE_COPY: Record<string, PhraseCopy> = PHRASES.codes

const PATTERN_RULES = PHRASES.patterns.map((rule) => ({
  ...rule,
  re: new RegExp(rule.match, 'i'),
}))

const SNAKE_CODE_RE = /^[a-z][a-z0-9_]{2,63}$/
const TRACE_RE = /\n(?:Traceback|  File )/m
const API_PREFIX_RE = /^(?:GET|POST|PATCH|PUT|DELETE) \S+ failed:\s*/i

function copyForCode(code: string): PhraseCopy | undefined {
  const trimmed = code.trim()
  if (!trimmed) return undefined
  if (CODE_COPY[trimmed]) return CODE_COPY[trimmed]
  if (trimmed.startsWith('http_')) {
    const status = Number(trimmed.slice(5))
    if (HTTP_COPY[status]) return HTTP_COPY[status]
  }
  return undefined
}

function humanizeCode(code: string): string {
  const trimmed = code.trim()
  if (!trimmed) return PHRASES.fallback.message
  const copy = copyForCode(trimmed)
  if (copy) return copy.message
  if (SNAKE_CODE_RE.test(trimmed)) {
    return trimmed.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) + '.'
  }
  return trimmed
}

function hintForCode(code: string): string | undefined {
  return copyForCode(code)?.hint
}

function actionLabelForCode(code: string): string | undefined {
  return copyForCode(code)?.actionLabel
}

function scrubInternalText(raw: string): string {
  let text = raw.trim()
  if (!text) return ''
  if (TRACE_RE.test(text)) {
    text = text.split(TRACE_RE)[0]?.trim() ?? text
  }
  if (text.includes('\n')) {
    text = text.split('\n', 1)[0]?.trim() ?? text
  }
  return text
}

function isLikelyInternalError(text: string): boolean {
  const trimmed = scrubInternalText(text)
  if (!trimmed) return true
  if (TRACE_RE.test(text)) return true
  if (/PermissionError|Traceback|  File "/i.test(text)) return true
  if (/runtime profile create failed:/i.test(text) && trimmed.length > 120) return true
  if (trimmed.includes('/') && trimmed.includes('.py')) return true
  return false
}

function matchPattern(text: string): { code: string; copy: PhraseCopy } | null {
  const sample = scrubInternalText(text)
  if (!sample) return null
  for (const rule of PATTERN_RULES) {
    if (!rule.re.test(sample) && !rule.re.test(text)) continue
    const copy = copyForCode(rule.code)
    if (copy) return { code: rule.code, copy }
    if (rule.code.startsWith('http_')) {
      const status = Number(rule.code.slice(5))
      const httpCopy = HTTP_COPY[status]
      if (httpCopy) return { code: rule.code, copy: httpCopy }
    }
  }
  return null
}

function resolveRawError(raw: string, context?: string): WorkframeNoticeInfo {
  const scrubbed = scrubInternalText(raw)
  const apiBody = scrubbed.replace(API_PREFIX_RE, '').trim() || scrubbed

  if (CODE_COPY[apiBody]) {
    const copy = CODE_COPY[apiBody]
    return {
      tone: 'caution',
      code: apiBody,
      message: copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
      action: DEFAULT_ACTIONS[apiBody],
    }
  }

  const pattern = matchPattern(apiBody)
  if (pattern) {
    return {
      tone: 'caution',
      code: pattern.code,
      message: pattern.copy.message,
      hint: pattern.copy.hint,
      actionLabel: pattern.copy.actionLabel,
      action: DEFAULT_ACTIONS[pattern.code],
    }
  }

  if (SNAKE_CODE_RE.test(apiBody) && copyForCode(apiBody)) {
    const copy = copyForCode(apiBody)!
    return {
      tone: 'caution',
      code: apiBody,
      message: copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
      action: DEFAULT_ACTIONS[apiBody],
    }
  }

  const contextCopy = context ? PHRASES.contexts?.[context.trim().toLowerCase().replace(/\s+/g, '_')] : undefined
  if (contextCopy) {
    return {
      tone: 'caution',
      code: 'request_failed',
      message: contextCopy.message,
      hint: contextCopy.hint ?? PHRASES.fallback.hint,
    }
  }

  if (isLikelyInternalError(apiBody)) {
    return {
      tone: 'caution',
      code: 'request_failed',
      message: PHRASES.internal.message,
      hint: PHRASES.internal.hint,
    }
  }

  return {
    tone: 'caution',
    message: humanizeCode(apiBody) === apiBody ? apiBody : humanizeCode(apiBody),
    hint: hintForCode(apiBody),
    actionLabel: actionLabelForCode(apiBody),
  }
}

const DEFAULT_ACTIONS: Record<string, WorkframeNoticeAction> = {
  no_llm_provider_for_user: { type: 'open_settings', tab: 'providers' },
  no_llm_provider: { type: 'open_settings', tab: 'providers' },
  provider_invalid_key: { type: 'open_settings', tab: 'providers' },
  provider_no_credits: { type: 'external_link', url: 'https://openrouter.ai/credits', label: 'Add credits' },
  model_unavailable: { type: 'open_settings', tab: 'model' },
  model_invalid_id: { type: 'open_settings', tab: 'model' },
  model_not_available: { type: 'open_settings', tab: 'model' },
  provider_rate_limited: { type: 'open_settings', tab: 'model' },
  provider_empty_reply: { type: 'open_settings', tab: 'model' },
  provider_rejected: { type: 'open_settings', tab: 'providers' },
  invalid_lease: { type: 'retry' },
  concierge_add_keys: { type: 'open_settings', tab: 'providers' },
  concierge_change_model: { type: 'open_settings', tab: 'model' },
  concierge_getting_started: { type: 'open_settings', tab: 'providers' },
  concierge_diagnose: { type: 'open_settings', tab: 'providers' },
  agent_no_reply: { type: 'open_settings', tab: 'providers' },
  agent_provider_unreachable: { type: 'open_settings', tab: 'providers' },
}

function parseNoticeAction(raw: unknown): WorkframeNoticeAction | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const row = raw as Record<string, unknown>
  const type = String(row.type || '').trim()
  if (type === 'open_settings') {
    const tab = String(row.tab || 'providers').trim()
    if (tab === 'model') return { type: 'open_settings', tab: 'model' }
    if (tab === 'profile' || tab === 'agents' || tab === 'appearance' || tab === 'connect') {
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
  const copy = code ? copyForCode(code) : undefined
  const message = String(data.message || data.text || '').trim() || copy?.message || ''
  const rawError = String(data.error || '').trim()
  const hint = String(data.hint || copy?.hint || '').trim() || undefined
  const action = parseNoticeAction(data.action) || (code ? DEFAULT_ACTIONS[code] : undefined)
  const secondary_action = parseNoticeAction(data.secondary_action)

  if (!message && rawError) {
    return resolveRawError(rawError, code || undefined)
  }

  return {
    tone: 'caution',
    code: code || undefined,
    message: message || PHRASES.fallback.message,
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
  for (const key of ['message', 'detail']) {
    const value = data[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  const error = data.error
  if (typeof error === 'string' && error.trim()) {
    const trimmed = error.trim()
    if (copyForCode(trimmed)) return copyForCode(trimmed)!.message
    if (!isLikelyInternalError(trimmed)) return trimmed
  }
  return ''
}

function bodyCode(data: Record<string, unknown> | null): string | undefined {
  if (!data) return undefined
  const explicit = data.code
  if (typeof explicit === 'string' && explicit.trim()) return explicit.trim()
  const error = data.error
  if (typeof error === 'string' && error.trim()) {
    const trimmed = error.trim()
    if (copyForCode(trimmed) || SNAKE_CODE_RE.test(trimmed)) return trimmed
  }
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

export function isProviderSetupError(message: string | WorkframeNoticeInfo | null | undefined): boolean {
  if (!message) return false
  if (typeof message === 'object') {
    return (
      message.code === 'no_llm_provider_for_user' ||
      message.code === 'no_llm_provider' ||
      isProviderSetupError(message.message)
    )
  }
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
  if (/invalid.*(api[_ ]?key|token)|authentication failed|incorrect api key|unauthorized|401|403|user not found/i.test(trimmed)) {
    const copy = CODE_COPY.provider_invalid_key
    return {
      tone: 'caution',
      code: 'provider_invalid_key',
      message: copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
      action: DEFAULT_ACTIONS.provider_invalid_key,
    }
  }
  if (/model.*(not found|does not exist|unknown)|invalid model/i.test(trimmed)) {
    const copy = CODE_COPY.model_not_available
    return {
      tone: 'caution',
      code: 'model_not_available',
      message: copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
      action: DEFAULT_ACTIONS.model_not_available,
    }
  }
  return null
}

function withContext(info: WorkframeNoticeInfo, context?: string): WorkframeNoticeInfo {
  if (!context?.trim()) return info
  if (info.code && info.code !== 'request_failed') return info
  const key = context.trim().toLowerCase().replace(/\s+/g, '_')
  const contextCopy = PHRASES.contexts?.[key]
  if (!contextCopy) return info
  return {
    ...info,
    message: contextCopy.message || info.message,
    hint: contextCopy.hint || info.hint,
  }
}

export function formatWorkframeError(err: unknown, context?: string): WorkframeNoticeInfo {
  if (err instanceof WorkframeApiError) {
    return withContext(err.notice, context)
  }
  if (err && typeof err === 'object' && 'message' in err && 'tone' in err) {
    return withContext(err as WorkframeNoticeInfo, context)
  }

  if (err instanceof Response) {
    const info = formatHttpStatus(err.status)
    return withContext(info, context)
  }

  const raw = err instanceof Error ? err.message.trim() : String(err ?? '').trim()
  if (!raw || raw === 'Error' || raw === 'HTTP undefined') {
    const contextCopy = context ? PHRASES.contexts?.[context.trim().toLowerCase().replace(/\s+/g, '_')] : undefined
    return {
      tone: 'caution',
      message: contextCopy?.message || PHRASES.fallback.message,
      hint: contextCopy?.hint || PHRASES.fallback.hint,
    }
  }

  const httpMatch = raw.match(/^HTTP (\d{3})$/)
  if (httpMatch) {
    return withContext(formatHttpStatus(Number(httpMatch[1])), context)
  }

  return withContext(resolveRawError(raw, context), context)
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
  let code = bodyCode(data)
  let hint = bodyHint(data)
  let message = bodyMessage(data)

  if (!message && code) {
    message = copyForCode(code)?.message || humanizeCode(code)
  }
  if (!hint && code) {
    hint = hintForCode(code)
  }
  if (!code && data) {
    const rawError = typeof data.error === 'string' ? data.error : ''
    const pattern = rawError ? matchPattern(rawError) : null
    if (pattern) {
      code = pattern.code
      message = pattern.copy.message
      hint = pattern.copy.hint
    } else if (rawError && isLikelyInternalError(rawError)) {
      code = 'request_failed'
      message = PHRASES.internal.message
      hint = PHRASES.internal.hint
    }
  }
  if (code === 'private_workspace' && typeof data?.message === 'string' && data.message.trim()) {
    message = data.message.trim()
  }
  if (!message && HTTP_COPY[status]) {
    message = HTTP_COPY[status].message
  }
  if (!message) {
    message = status ? `Request failed (HTTP ${status}).` : PHRASES.fallback.message
  }

  return {
    tone: 'caution',
    status,
    code,
    message,
    hint: hint || HTTP_COPY[status]?.hint,
    actionLabel: code ? actionLabelForCode(code) : undefined,
    action: code ? DEFAULT_ACTIONS[code] : undefined,
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
    return noticeMessage(formatWorkframeError(raw))
  }
  const warning = String(payload.warning ?? '').trim()
  if (warning) {
    const provider = providerFailureNotice(warning)
    if (provider) return noticeMessage(provider)
    return noticeMessage(formatWorkframeError(warning))
  }
  const status = String(payload.status ?? '').trim().toLowerCase()
  if (status === 'error') {
    const copy = CODE_COPY.agent_provider_unreachable
    return noticeMessage({
      tone: 'caution',
      code: 'agent_provider_unreachable',
      message: copy.message,
      hint: copy.hint,
      actionLabel: copy.actionLabel,
    })
  }
  if (status === 'interrupted') {
    return noticeMessage({
      tone: 'caution',
      code: 'turn_interrupted',
      message: CODE_COPY.turn_interrupted.message,
    })
  }
  const copy = CODE_COPY.agent_error_unknown
  return noticeMessage({
    tone: 'caution',
    code: 'agent_error_unknown',
    message: copy.message,
    hint: copy.hint,
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
  const copy = CODE_COPY.agent_no_reply
  return noticeMessage({
    tone: 'caution',
    code: 'agent_no_reply',
    message: copy.message,
    hint: copy.hint,
    actionLabel: copy.actionLabel,
  })
}

export function validateAvatarFile(file: File): WorkframeNoticeInfo | null {
  if (!file.type.startsWith('image/')) {
    const copy = CODE_COPY.avatar_type
    return {
      tone: 'caution',
      message: copy.message,
      hint: copy.hint,
      code: 'avatar_type',
    }
  }
  if (file.size > AVATAR_MAX_FILE_BYTES) {
    const copy = CODE_COPY.avatar_too_large
    return {
      tone: 'caution',
      message: copy.message,
      hint: copy.hint,
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
