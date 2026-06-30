import { apiGet } from '@/lib/apiClient'
import type { HermesProfile } from '@/lib/hermesProfile'

type AgentsResponse = {
  ok?: boolean
  crew?: HermesProfile[]
}

let agentsPromise: Promise<AgentsResponse> | null = null

export async function fetchWorkframeAgents(): Promise<AgentsResponse> {
  if (!agentsPromise) {
    agentsPromise = apiGet<AgentsResponse>('/api/agents').catch((err) => {
      agentsPromise = null
      throw err
    })
  }
  return agentsPromise
}

export function invalidateWorkframeAgentsCache(): void {
  agentsPromise = null
}
