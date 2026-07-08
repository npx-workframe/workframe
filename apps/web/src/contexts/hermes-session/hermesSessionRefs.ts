import { useRef, type MutableRefObject } from 'react'

import type { ChatMessage } from '@/lib/chatTypes'

export type HermesSessionRefs = {
  profileRef: MutableRefObject<string>
  templateProfileRef: MutableRefObject<string>
  roomIdRef: MutableRefObject<string>
  gatewaySidRef: MutableRefObject<string | null>
  stateDbSidRef: MutableRefObject<string | null>
  turnActiveRef: MutableRefObject<boolean>
  streamMessageIdRef: MutableRefObject<string | null>
  pendingOutboundRef: MutableRefObject<string | null>
  sourceIdRef: MutableRefObject<string>
  clientIdRef: MutableRefObject<string>
  nativeProfileRef: MutableRefObject<string>
  finalizedTurnIdsRef: MutableRefObject<Set<string>>
  prevRoomKeyRef: MutableRefObject<string>
  bindGenRef: MutableRefObject<number>
  initRef: MutableRefObject<boolean>
  llmReadyRef: MutableRefObject<boolean | null>
}

export function useHermesSessionRefs(): HermesSessionRefs {
  return {
    profileRef: useRef(''),
    templateProfileRef: useRef(''),
    roomIdRef: useRef(''),
    gatewaySidRef: useRef<string | null>(null),
    stateDbSidRef: useRef<string | null>(null),
    turnActiveRef: useRef(false),
    streamMessageIdRef: useRef<string | null>(null),
    pendingOutboundRef: useRef<string | null>(null),
    sourceIdRef: useRef('ui'),
    clientIdRef: useRef('default'),
    nativeProfileRef: useRef(''),
    finalizedTurnIdsRef: useRef(new Set<string>()),
    prevRoomKeyRef: useRef(''),
    bindGenRef: useRef(0),
    initRef: useRef(false),
    llmReadyRef: useRef<boolean | null>(null),
  }
}

export type BoundSessionPayload = {
  sessionId: string
  profile: string
  templateProfile: string
  agentDisplayName: string
  messages: ChatMessage[]
}
