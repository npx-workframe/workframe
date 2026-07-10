export type ProviderConnectReturn = {
  provider: string
  status: 'ok' | 'error'
  message: string
}

export function peekProviderConnectReturn(): ProviderConnectReturn | null {
  const params = new URLSearchParams(window.location.search)
  const provider = params.get('provider_connect')?.trim()
  if (!provider) return null
  const status = params.get('status') === 'ok' ? 'ok' : 'error'
  const raw = params.get('message')?.trim()
  const message =
    raw ||
    (status === 'ok' ? `${provider} connected` : `${provider} connection failed`)
  return { provider, status, message }
}

export function clearProviderConnectReturn(): void {
  const params = new URLSearchParams(window.location.search)
  if (!params.has('provider_connect')) return
  params.delete('provider_connect')
  params.delete('status')
  params.delete('message')
  const query = params.toString()
  const next = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`
  window.history.replaceState({}, '', next)
}
