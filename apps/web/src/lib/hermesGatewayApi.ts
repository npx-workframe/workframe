import { fetchHermesBootstrap } from '@/lib/hermesDashboardApi'
import { parseHermesEvent, type HermesEventFrame } from '@/lib/hermesEvents'

type JsonRpcResponse = {
  id?: number
  method?: string
  params?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: { message?: string; code?: number }
}

type PendingRpc = {
  resolve: (value: Record<string, unknown>) => void
  reject: (err: Error) => void
  timer: number
}

export type GatewayEventListener = (frame: HermesEventFrame) => void

let rpcId = 1
let wsPromise: Promise<WebSocket> | null = null
let gatewayWs: WebSocket | null = null
let activeWsPath = ''
const pendingRpc = new Map<number, PendingRpc>()
const eventListeners = new Set<GatewayEventListener>()

function wsUrlForPath(wsPath: string, token: string): string {
  const url = new URL(wsPath, window.location.origin)
  url.searchParams.set('token', token)
  const proto = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${url.host}${url.pathname}${url.search}`
}

function rejectPendingRpc(reason: string): void {
  for (const [id, pending] of pendingRpc) {
    window.clearTimeout(pending.timer)
    pending.reject(new Error(reason))
    pendingRpc.delete(id)
  }
}

export function closeGatewayWs(): void {
  if (gatewayWs) {
    gatewayWs.onclose = null
    gatewayWs.close()
    gatewayWs = null
  }
  wsPromise = null
  activeWsPath = ''
  rejectPendingRpc('Hermes gateway connection closed')
}

function dispatchGatewayMessage(raw: string): void {
  let frame: JsonRpcResponse
  try {
    frame = JSON.parse(raw) as JsonRpcResponse
  } catch {
    return
  }

  if (frame.method === 'event') {
    const parsed = parseHermesEvent(raw)
    if (parsed) {
      for (const listener of eventListeners) listener(parsed)
    }
    return
  }

  if (frame.id == null || !pendingRpc.has(frame.id)) return

  const pending = pendingRpc.get(frame.id)!
  pendingRpc.delete(frame.id)
  window.clearTimeout(pending.timer)

  if (frame.error) {
    pending.reject(new Error(frame.error.message ?? 'request failed'))
    return
  }

  pending.resolve((frame.result ?? {}) as Record<string, unknown>)
}

async function openGatewayWs(): Promise<WebSocket> {
  if (gatewayWs && gatewayWs.readyState === WebSocket.OPEN) return gatewayWs

  if (wsPromise) {
    const existing = await wsPromise
    if (existing.readyState === WebSocket.OPEN) return existing
    wsPromise = null
  }

  wsPromise = (async () => {
    const boot = await fetchHermesBootstrap()
    if (!boot.ok || !boot.token) {
      throw new Error(boot.error || 'profile_dashboard_unavailable')
    }

    if (gatewayWs && gatewayWs.readyState === WebSocket.OPEN && activeWsPath === boot.wsPath) {
      return gatewayWs
    }

    closeGatewayWs()
    activeWsPath = boot.wsPath
    const wsUrl = wsUrlForPath(boot.wsPath, boot.token)
    const ws = new WebSocket(wsUrl)

    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.onerror = () => reject(new Error('Hermes gateway connection failed'))
    })

    ws.onmessage = (event) => dispatchGatewayMessage(String(event.data))
    ws.onclose = () => {
      gatewayWs = null
      wsPromise = null
      activeWsPath = ''
      rejectPendingRpc('Hermes gateway connection closed')
    }

    gatewayWs = ws
    return ws
  })()

  return wsPromise
}

/** Live agent events (`message.delta`, `message.complete`, …) arrive on /api/ws, not /api/events. */
export function subscribeGatewayEvents(listener: GatewayEventListener): () => void {
  eventListeners.add(listener)
  void openGatewayWs().catch(() => {
    // Connection errors surface on the next RPC/submit attempt.
  })
  return () => eventListeners.delete(listener)
}

export async function hermesRpc<T extends Record<string, unknown>>(
  method: string,
  params: Record<string, unknown> = {},
  timeoutMs = 30_000,
): Promise<T> {
  const ws = await openGatewayWs()
  const id = rpcId++

  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      pendingRpc.delete(id)
      reject(new Error(`${method} timed out`))
    }, timeoutMs)

    pendingRpc.set(id, {
      resolve: (result) => resolve(result as T),
      reject,
      timer,
    })

    ws.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }))
  })
}

export type GatewaySessionCreate = {
  session_id: string
  info?: Record<string, unknown>
}

export type GatewaySessionResume = {
  session_id: string
  resumed?: string
  message_count?: number
}

export type GatewayMostRecent = {
  session_id: string | null
  title?: string
  source?: string
}

const SESSION_BUSY_RE = /session busy|waiting for model response/i

function isSessionBusyError(err: unknown): boolean {
  return err instanceof Error && SESSION_BUSY_RE.test(err.message)
}

function isSessionNotFoundError(err: unknown): boolean {
  return err instanceof Error && /session not found/i.test(err.message)
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export type GatewaySessionBind = {
  gatewaySid: string
  stateDbSessionId: string
}

export type GatewaySessionActivate = {
  session_key?: string
  session_id?: string
}

/** Read the state.db session key bound to a live gateway session. */
export async function bindGatewaySession(gatewaySessionId: string): Promise<string> {
  const result = await hermesRpc<GatewaySessionActivate>('session.activate', {
    session_id: gatewaySessionId,
  })
  const key = String(result.session_key ?? '').trim()
  if (!key) throw new Error('session.activate returned no session_key')
  return key
}

/** Fresh in-memory gateway session (Hermes session.create — no state.db resume). */
export async function createGatewaySession(): Promise<GatewaySessionBind> {
  const result = await hermesRpc<GatewaySessionCreate>('session.create', {})
  const gatewaySid = result.session_id
  if (!gatewaySid) throw new Error('session.create returned no gateway session id')
  const stateDbSessionId = await bindGatewaySession(gatewaySid)
  return { gatewaySid, stateDbSessionId }
}

/** Most recent human-facing Hermes session in state.db (may be null). */
export async function fetchMostRecentSessionId(): Promise<string | null> {
  const result = await hermesRpc<GatewayMostRecent>('session.most_recent', {})
  const sid = result.session_id
  return sid ? String(sid) : null
}

/** Bind tui_gateway in-memory session to a Hermes state.db session id. */
export async function resumeGatewaySession(stateDbSessionId: string): Promise<GatewaySessionBind> {
  const result = await hermesRpc<GatewaySessionResume>('session.resume', {
    session_id: stateDbSessionId,
  })
  const gatewaySid = result.session_id
  if (!gatewaySid) throw new Error('session.resume returned no gateway session id')
  const stateDbId = String(result.resumed ?? stateDbSessionId).trim()
  return { gatewaySid, stateDbSessionId: stateDbId }
}

export async function interruptGatewaySession(gatewaySessionId: string): Promise<void> {
  try {
    await hermesRpc('session.interrupt', { session_id: gatewaySessionId })
  } catch {
    // Best effort — stale or missing sessions are handled on retry.
  }
}

export async function submitPrompt(gatewaySessionId: string, text: string): Promise<void> {
  await hermesRpc('prompt.submit', { session_id: gatewaySessionId, text })
}

/** Submit with Hermes-native recovery for stale busy gateway sessions. */
export async function submitPromptResilient(
  gatewaySessionId: string,
  text: string,
  refreshGatewaySession?: () => Promise<string>,
): Promise<string> {
  let sid = gatewaySessionId

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await submitPrompt(sid, text)
      return sid
    } catch (err) {
      if (isSessionNotFoundError(err) && refreshGatewaySession) {
        sid = await refreshGatewaySession()
        continue
      }
      if (isSessionBusyError(err) && attempt < 2) {
        await interruptGatewaySession(sid)
        await sleep(300)
        continue
      }
      throw err
    }
  }

  throw new Error('prompt.submit failed after retries')
}

export type ImageAttachResult = {
  attached?: boolean
  path?: string
  name?: string
  text?: string
  message?: string
}

export async function attachImagePath(
  gatewaySessionId: string,
  path: string,
): Promise<ImageAttachResult> {
  return hermesRpc<ImageAttachResult>('image.attach', {
    session_id: gatewaySessionId,
    path,
  })
}
