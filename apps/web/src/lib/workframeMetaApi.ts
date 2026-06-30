import { apiGet } from '@/lib/apiClient'

export type WorkframeMeta = {
  ok?: boolean
  project_name?: string
  install_id?: string
  native_profile?: string
  native_agent_name?: string
  native_model?: string
}

let metaPromise: Promise<WorkframeMeta> | null = null

export async function fetchWorkframeMeta(): Promise<WorkframeMeta> {
  if (!metaPromise) {
    metaPromise = apiGet<WorkframeMeta>('/api/meta').catch((err) => {
      metaPromise = null
      throw err
    })
  }
  return metaPromise
}

export function invalidateWorkframeMetaCache(): void {
  metaPromise = null
}
