export type SurfaceLink = {
  id: 'dashboard' | 'api' | 'setup'
  label: string
  href: string
}

export type SurfaceLinkOptions = {
  includeDashboard?: boolean
}

function surfaceUrl(fullUrl: string | undefined, port: string | undefined, defaultPort: number) {
  const trimmedUrl = fullUrl?.trim()
  if (trimmedUrl) return trimmedUrl

  const trimmedPort = port?.trim() || String(defaultPort)
  return `http://127.0.0.1:${trimmedPort}`
}

export function getSurfaceLinks(options?: SurfaceLinkOptions): SurfaceLink[] {
  const links: SurfaceLink[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      href: '/hermes-dashboard/',
    },
    {
      id: 'api',
      label: 'Auth/UI',
      href: surfaceUrl(
        import.meta.env.VITE_WORKFRAME_API_URL,
        import.meta.env.VITE_WORKFRAME_API_PORT,
        18644,
      ),
    },
    {
      id: 'setup',
      label: 'Open setup',
      href: surfaceUrl(
        import.meta.env.VITE_WORKFRAME_SETUP_URL,
        import.meta.env.VITE_WORKFRAME_SETUP_PORT ??
          import.meta.env.VITE_WORKFRAME_DASHBOARD_PORT,
        19119,
      ),
    },
  ]
  if (options?.includeDashboard === false) {
    return links.filter((link) => link.id !== 'dashboard')
  }
  return links
}
