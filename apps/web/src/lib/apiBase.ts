export function apiBaseUrl(): string {
  return (import.meta.env.VITE_WORKFRAME_API_BASE_URL || '').trim().replace(/\/+$/, '')
}

export function apiUrl(path: string): string {
  const base = apiBaseUrl()
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${base}${normalized}`
}

export function workframeApiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return apiUrl(normalized.startsWith('/api') ? normalized : `/api${normalized}`)
}
