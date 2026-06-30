const SESSION_KEY_BASE = 'workframe.session_id'
const INSTALL_SCOPE_KEY = 'workframe.install_id'

function readInstallScope(): string {
  try {
    return sessionStorage.getItem(INSTALL_SCOPE_KEY) || ''
  } catch {
    return ''
  }
}

function sessionKey(): string {
  const installId = readInstallScope()
  return installId ? `${SESSION_KEY_BASE}.${installId}` : SESSION_KEY_BASE
}

/** Clear session when install identity changes (same port, fresh wipe). */
export function syncSessionInstallScope(installId: string): void {
  const next = String(installId || '').trim()
  if (!next) return
  try {
    const prev = sessionStorage.getItem(INSTALL_SCOPE_KEY) || ''
    if (prev && prev !== next) {
      sessionStorage.removeItem(`${SESSION_KEY_BASE}.${prev}`)
      sessionStorage.removeItem(SESSION_KEY_BASE)
    }
    sessionStorage.setItem(INSTALL_SCOPE_KEY, next)
  } catch {
    // ponytail: private mode may block storage
  }
}

function readSession(): string {
  try {
    return sessionStorage.getItem(sessionKey()) || ''
  } catch {
    return ''
  }
}

function writeSession(value: string): void {
  try {
    const key = sessionKey()
    if (value) sessionStorage.setItem(key, value)
    else sessionStorage.removeItem(key)
  } catch {
    // ponytail: private mode may block storage; HttpOnly cookie is primary
  }
}

/** One-time migrate from localStorage → sessionStorage (tab-scoped). */
function migrateLegacySession(): void {
  try {
    const legacy = localStorage.getItem(SESSION_KEY_BASE)
    if (legacy && !readSession()) {
      writeSession(legacy)
      localStorage.removeItem(SESSION_KEY_BASE)
    }
    localStorage.removeItem('workframe.refresh_token')
  } catch {
    // ignore
  }
}

export function getStoredSessionId(): string {
  migrateLegacySession()
  return readSession()
}

/** Refresh tokens live server-side only (HttpOnly cookie path). */
export function getStoredRefreshToken(): string {
  return ''
}

export function setStoredSessionTokens(sessionId: string, _refreshToken?: string): void {
  writeSession(sessionId)
}

export function setStoredSessionId(id: string): void {
  setStoredSessionTokens(id)
}

export function clearStoredSessionTokens(): void {
  writeSession('')
  try {
    localStorage.removeItem(SESSION_KEY_BASE)
    localStorage.removeItem('workframe.refresh_token')
    const installId = readInstallScope()
    if (installId) sessionStorage.removeItem(`${SESSION_KEY_BASE}.${installId}`)
    sessionStorage.removeItem(SESSION_KEY_BASE)
  } catch {
    // ignore
  }
}

export function workframeAuthHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init)
  const sid = getStoredSessionId()
  if (sid) headers.set('X-Workframe-Session', sid)
  return headers
}
