import type { ChatMessage } from '@/lib/chatTypes'
import type { HermesModelsResponse } from '@/lib/hermesCatalogApi'
import { peekCachedSessionProfile } from '@/lib/workframeAuthApi'
import type { WorkspaceRoom } from '@/lib/workframeAuthApi'

function projectKey(): string {
  return import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
}

function laneKey(workspaceId: string, userId: string): string {
  return `workframe.activeLane:${projectKey()}:${workspaceId}:${userId}`
}

function roomsKey(workspaceId: string): string {
  return `workframe.cachedRooms:${projectKey()}:${workspaceId}`
}

function messagesKey(roomId: string, sessionId: string): string {
  return `workframe.cachedMessages:${projectKey()}:${roomId}:${sessionId.trim()}`
}

function roomBindKey(roomId: string): string {
  return `workframe.cachedRoomBind:${projectKey()}:${roomId}`
}

function modelsKey(profile: string): string {
  return `workframe.cachedModels:${projectKey()}:${profile.trim()}`
}

/** Room bind hint — instant reopen; server revalidates in background. */
export type CachedRoomBind = {
  sessionId: string
  profile: string
  templateProfile: string
  agentDisplayName: string
  llmReady: boolean
  savedAt: number
}

const BIND_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000
const MODEL_CACHE_MAX_AGE_MS = 10 * 60 * 1000

/** One lane hint per user — room only; session comes from server bind. */
export type ActiveLaneHint = {
  roomId: string
  savedAt: number
  room?: WorkspaceRoom
}

function readJson<T>(key: string): T | null {
  if (!key || typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

function writeJson(key: string, value: unknown): void {
  if (!key || typeof window === 'undefined') return
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // quota or privacy mode
  }
}

function laneIds(): { workspaceId: string; userId: string } {
  const me = peekCachedSessionProfile()
  const workspaceId =
    me?.current_workspace?.id ?? me?.default_workspace?.id ?? me?.workspaces?.[0]?.id ?? ''
  const userId = me?.user?.user_id ?? ''
  return { workspaceId, userId }
}

export function readActiveLaneHint(workspaceId: string, userId: string): ActiveLaneHint | null {
  return readJson<ActiveLaneHint>(laneKey(workspaceId, userId))
}

/** Single lane writer — reload hint is roomId only; server owns session via room_sessions. */
export function writeActiveLane(
  hint: {
    workspaceId?: string
    userId?: string
    roomId: string
    room?: WorkspaceRoom
  },
): void {
  const workspaceId = hint.workspaceId ?? laneIds().workspaceId
  const userId = hint.userId ?? laneIds().userId
  if (!workspaceId || !userId || !hint.roomId) return
  const prev = readActiveLaneHint(workspaceId, userId)
  writeJson(laneKey(workspaceId, userId), {
    roomId: hint.roomId,
    savedAt: Date.now(),
    room: hint.room ?? (prev?.roomId === hint.roomId ? prev.room : undefined),
  })
}

// ponytail: one-shot migrate legacy bindHint keys from the perf pass
if (typeof window !== 'undefined') {
  const drop: string[] = []
  const prefix = `workframe.bindHint:${projectKey()}:`
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key?.startsWith(prefix)) drop.push(key)
  }
  for (const key of drop) localStorage.removeItem(key)
}

export function readCachedRooms(workspaceId: string): WorkspaceRoom[] {
  const data = readJson<{ rooms: WorkspaceRoom[] }>(roomsKey(workspaceId))
  return data?.rooms ?? []
}

export function writeCachedRooms(workspaceId: string, rooms: WorkspaceRoom[]): void {
  writeJson(roomsKey(workspaceId), { rooms, savedAt: Date.now() })
}

export function readCachedRoomBind(roomId: string): CachedRoomBind | null {
  if (!roomId.trim()) return null
  const data = readJson<CachedRoomBind>(roomBindKey(roomId))
  if (!data?.sessionId?.trim()) return null
  if (Date.now() - (data.savedAt || 0) > BIND_CACHE_MAX_AGE_MS) return null
  return data
}

export function writeCachedRoomBind(roomId: string, bind: Omit<CachedRoomBind, 'savedAt'>): void {
  if (!roomId.trim() || !bind.sessionId.trim()) return
  writeJson(roomBindKey(roomId), { ...bind, savedAt: Date.now() })
}

export function clearCachedRoomBind(roomId: string): void {
  if (!roomId.trim() || typeof window === 'undefined') return
  try {
    localStorage.removeItem(roomBindKey(roomId))
  } catch {
    // ignore
  }
}

export function peekCachedHermesModels(profile: string): HermesModelsResponse | null {
  const key = profile.trim()
  if (!key) return null
  const data = readJson<{ models: HermesModelsResponse; savedAt: number }>(modelsKey(key))
  if (!data?.models?.ok) return null
  if (Date.now() - (data.savedAt || 0) > MODEL_CACHE_MAX_AGE_MS) return null
  return data.models
}

export function writeCachedHermesModels(profile: string, models: HermesModelsResponse): void {
  const key = profile.trim()
  if (!key || !models.ok) return
  writeJson(modelsKey(key), { models, savedAt: Date.now() })
}

export function clearCachedHermesModels(profile: string): void {
  const key = profile.trim()
  if (!key || typeof window === 'undefined') return
  try {
    localStorage.removeItem(modelsKey(key))
  } catch {
    // ignore
  }
}

const MAX_CACHED_MSGS = 80

export function readCachedMessages(roomId: string, sessionId: string): ChatMessage[] {
  const sid = sessionId.trim()
  if (!sid) return []
  const data = readJson<{ messages: ChatMessage[] }>(messagesKey(roomId, sid))
  const msgs = data?.messages ?? []
  return msgs.filter((m) => !m.ephemeral).slice(-MAX_CACHED_MSGS)
}

export function writeCachedMessages(roomId: string, sessionId: string, messages: ChatMessage[]): void {
  const sid = sessionId.trim()
  if (!sid) return
  const stable = messages.filter((m) => !m.ephemeral).slice(-MAX_CACHED_MSGS)
  if (!stable.length) return
  writeJson(messagesKey(roomId, sid), { messages: stable, savedAt: Date.now() })
}

export function clearCachedMessages(roomId: string, sessionId?: string): void {
  if (typeof window === 'undefined' || !roomId) return
  try {
    if (sessionId?.trim()) {
      localStorage.removeItem(messagesKey(roomId, sessionId))
      return
    }
    const prefix = `workframe.cachedMessages:${projectKey()}:${roomId}:`
    const drop: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith(prefix)) drop.push(key)
    }
    for (const key of drop) localStorage.removeItem(key)
  } catch {
    // ignore
  }
}
