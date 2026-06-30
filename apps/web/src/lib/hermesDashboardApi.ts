import { apiGet } from '@/lib/apiClient'

type BootstrapResponse = {
  ok: boolean
  dashboard_url?: string
  token?: string
  embedded_chat?: boolean
  error?: string
}

export type HermesBootstrap = {
  ok: boolean
  dashboardUrl: string
  wsPath: string
  token: string
  embeddedChat: boolean
  error?: string
}

function mapBootstrap(data: BootstrapResponse): HermesBootstrap {
  const dashboardPath = '/hermes-dashboard'
  return {
    ok: data.ok,
    dashboardUrl: data.dashboard_url || dashboardPath,
    wsPath: `${dashboardPath.replace(/\/$/, '')}/api/ws`,
    token: data.token || '',
    embeddedChat: Boolean(data.embedded_chat),
    error: data.error,
  }
}

export async function fetchHermesBootstrap(): Promise<HermesBootstrap> {
  const data = await apiGet<BootstrapResponse>('/api/hermes/bootstrap')
  return mapBootstrap(data)
}
