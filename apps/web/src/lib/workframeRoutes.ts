import { apiGet } from '@/lib/apiClient'

export type WorkframeRouteMode = 'lane'

export type WorkframeRoute = {
  id: string
  profile: string
  displayName: string
  role: string
  mode: WorkframeRouteMode
  avatarUrl?: string
  routeStatus?: string
}

type RoutesResponse = {
  ok: boolean
  default_profile?: string
  routes?: Array<{
    id?: string
    profile?: string
    display_name?: string
    displayName?: string
    role?: string
    mode?: string
    avatar_url?: string
    avatarUrl?: string
    avatar_id?: string
    route_status?: string
    routeStatus?: string
  }>
}

export function mapRoute(row: NonNullable<RoutesResponse['routes']>[number]): WorkframeRoute {
  const profile = String(row.profile || row.id || '')
  return {
    id: String(row.id || profile),
    profile,
    displayName: String(row.display_name || row.displayName || profile),
    role: String(row.role || ''),
    mode: 'lane',
    avatarUrl: row.avatar_url || row.avatarUrl,
    routeStatus: row.route_status || row.routeStatus,
  }
}

export async function fetchRoutes(): Promise<{ defaultProfile: string; routes: WorkframeRoute[] }> {
  const data = await apiGet<RoutesResponse>('/api/routes')
  const routes = (data.routes ?? []).map(mapRoute)
  return {
    defaultProfile: String(data.default_profile || routes[0]?.profile || ''),
    routes,
  }
}
