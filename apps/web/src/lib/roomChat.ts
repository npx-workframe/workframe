import type { WorkspaceRoom } from '@/lib/workframeAuthApi'
import { isAgentChatRoom } from '@/lib/agentProfile'

/** Shared channel/group/lane — humans + agents, @mention to invoke agents. */
export function isProjectRoom(room: WorkspaceRoom | null | undefined): boolean {
  if (!room) return false
  return room.room_type === 'channel' || room.room_type === 'group' || room.room_type === 'lane'
}

/** @deprecated Use isProjectRoom */
export const isSpaceRoom = isProjectRoom

/** Two humans only — SQLite messages, no standing agent lane. */
export function isHumanDmRoom(room: WorkspaceRoom | null | undefined): boolean {
  if (!room) return false
  return room.room_type === 'direct' && !isAgentChatRoom(room)
}

/** One human + one agent — Hermes-backed private lane (per-user keys). */
export function isAgentDmRoom(room: WorkspaceRoom | null | undefined): boolean {
  return isAgentChatRoom(room) && room?.room_type === 'direct'
}
