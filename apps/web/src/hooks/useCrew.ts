import { useCallback, useEffect, useState } from 'react'

import { fetchWorkframeAgents } from '@/lib/workframeAgentsApi'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAgentFromHermes, type WorkframeAgent } from '@/lib/hermesProfile'

function crewCacheKey(projectName: string): string {
  return `workframe.cachedCrew:${projectName}`
}

function readCachedCrew(projectName: string): WorkframeAgent[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(crewCacheKey(projectName))
    if (!raw) return []
    const data = JSON.parse(raw) as { crew?: WorkframeAgent[] }
    return data.crew ?? []
  } catch {
    return []
  }
}

function writeCachedCrew(projectName: string, crew: WorkframeAgent[]): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(crewCacheKey(projectName), JSON.stringify({ crew, savedAt: Date.now() }))
  } catch {
    // ignore quota failures
  }
}

export function useCrew(projectName: string) {
  const [crew, setCrew] = useState<WorkframeAgent[]>(() => readCachedCrew(projectName))
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const reload = useCallback(() => {
    setReloadToken((value) => value + 1)
  }, [])

  useEffect(() => {
    let cancelled = false
    void fetchWorkframeAgents()
      .then((data) => {
        if (cancelled) return
        const next = (data.crew ?? []).map(workframeAgentFromHermes)
        setError(null)
        setCrew(next)
        writeCachedCrew(projectName, next)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(formatWorkframeErrorMessage(err, 'Load agents'))
          if (!crew.length) setCrew([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectName, reloadToken])

  return { crew, error, reload }
}
