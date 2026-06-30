import { useEffect } from 'react'

import { applySiteMeta, fetchPublicSiteMeta } from '@/lib/siteMeta'

/** Sync document title, OG tags, favicon, and manifest link from the public BFF payload. */
export function useSiteMeta(enabled = true) {
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    void fetchPublicSiteMeta().then((meta) => {
      if (!cancelled && meta?.ok) applySiteMeta(meta)
    })
    return () => {
      cancelled = true
    }
  }, [enabled])
}
