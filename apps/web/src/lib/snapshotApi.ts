import { apiGet } from '@/lib/apiClient'
import type { HermesProfile } from '@/lib/hermesProfile'

export type SnapshotActivityRow = {
  agent_name?: string
  profile?: string
  task_description?: string
  status?: string
  model_used?: string
  created_at?: string
  source?: string
}

type SnapshotResponse = {
  crew?: HermesProfile[]
  activity?: SnapshotActivityRow[]
  native_model?: string
}

let snapshotPromise: Promise<SnapshotResponse> | null = null

export async function fetchSnapshot(): Promise<SnapshotResponse> {
  if (!snapshotPromise) {
    snapshotPromise = apiGet<SnapshotResponse>('/api/snapshot').catch((err) => {
      snapshotPromise = null
      throw err
    })
  }
  return snapshotPromise
}

export function invalidateSnapshotCache(): void {
  snapshotPromise = null
}

