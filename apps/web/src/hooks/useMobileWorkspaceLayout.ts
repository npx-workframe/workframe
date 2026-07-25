import { useEffect, useState } from 'react'

export const MOBILE_WORKSPACE_MAX_WIDTH = 939

const QUERY = `(max-width: ${MOBILE_WORKSPACE_MAX_WIDTH}px)`

export function useMobileWorkspaceLayout(): boolean {
  const [mobileLayout, setMobileLayout] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia(QUERY).matches
  })

  useEffect(() => {
    const media = window.matchMedia(QUERY)
    const onChange = (event: MediaQueryListEvent) => setMobileLayout(event.matches)
    media.addEventListener('change', onChange)
    setMobileLayout(media.matches)
    return () => media.removeEventListener('change', onChange)
  }, [])

  return mobileLayout
}
