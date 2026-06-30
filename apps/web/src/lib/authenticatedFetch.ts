import { apiUrl } from '@/lib/apiBase'
import { clearStoredSessionTokens, getStoredSessionId, setStoredSessionId, workframeAuthHeaders } from '@/lib/workframeSession'

export const WORKFRAME_SESSION_EXPIRED = 'workframe:session-expired'

let refreshInFlight: Promise<boolean> | null = null

async function refreshSessionOnce(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(apiUrl('/api/auth/refresh'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({}),
        })
        const text = await response.text()
        const data = text ? (JSON.parse(text) as Record<string, unknown>) : null
        if (!response.ok || !data) return false
        const sessionId = typeof data.session_id === 'string' ? data.session_id : ''
        if (!sessionId) return false
        setStoredSessionId(sessionId)
        return true
      } catch {
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

import { noticeMessage, parseApiErrorResponse } from '@/lib/workframeErrors'

export { parseApiErrorResponse } from '@/lib/workframeErrors'

export async function readApiError(response: Response): Promise<string> {
  const info = await parseApiErrorResponse(response)
  return noticeMessage(info)
}

/** Session-aware fetch: cookies + X-Workframe-Session, one refresh retry on 401. */
export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  allowRetry = true,
): Promise<Response> {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const response = await fetch(apiUrl(normalized), {
    ...init,
    headers: workframeAuthHeaders(init.headers),
    credentials: 'include',
  })
  if (response.status !== 401 || !allowRetry) return response
  const refreshed = await refreshSessionOnce()
  if (!refreshed) {
    const hadSession = Boolean(getStoredSessionId())
    clearStoredSessionTokens()
    if (hadSession && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(WORKFRAME_SESSION_EXPIRED))
    }
    return response
  }
  return authenticatedFetch(path, init, false)
}
