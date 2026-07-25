const IPHONE_STANDALONE_ATTR = 'data-iphone-standalone'

export function isIphoneStandalonePwa(): boolean {
  if (typeof window === 'undefined') return false

  const ua = window.navigator.userAgent
  if (!/iPhone/i.test(ua) || /iPad/i.test(ua)) return false

  const nav = window.navigator as Navigator & { standalone?: boolean }
  return (
    nav.standalone === true ||
    window.matchMedia('(display-mode: standalone)').matches
  )
}

export function syncIphoneStandalonePwaAttribute(): boolean {
  const active = isIphoneStandalonePwa()
  document.documentElement.toggleAttribute(IPHONE_STANDALONE_ATTR, active)
  return active
}
