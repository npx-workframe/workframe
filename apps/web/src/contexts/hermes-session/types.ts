import type { ChatMessage } from '@/lib/chatTypes'

export type HermesSessionState = {
  profile: string
  agentDisplayName: string
  nativeAgentName: string
  stateDbSessionId: string | null
  gatewaySessionId: string | null
  sessionReady: boolean
  connectError: string | null
  turnActive: boolean
  turnStatus: string | null
  messages: ChatMessage[]
  startNewSession: () => Promise<void>
  resumeSession: (sessionId: string) => Promise<void>
  reloadHistory: () => Promise<void>
  sendMessage: (text: string) => Promise<void>
  attachImage: (file: File) => Promise<void>
}
