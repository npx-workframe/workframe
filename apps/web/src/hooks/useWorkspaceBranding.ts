import { useEffect, useState } from 'react'

import { resolveLogoUrl } from '@/lib/avatarResolve'
import { DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

export type WorkspaceBranding = {
  name: string
  tagline: string
  logoUrl: string
}

export function useWorkspaceBranding(fallbackName: string): WorkspaceBranding {
  const [branding, setBranding] = useState<WorkspaceBranding>(() => ({
    name: fallbackName,
    tagline: '',
    logoUrl: DEFAULT_WORKSPACE_LOGO,
  }))

  useEffect(() => {
    let cancelled = false
    void workframeAuthApi
      .getMe()
      .then((me) => {
        if (cancelled) return
        const workspace = me.current_workspace ?? me.default_workspace ?? me.workspaces?.[0]
        setBranding({
          name: workspace?.display_name?.trim() || fallbackName,
          tagline: workspace?.tagline?.trim() || '',
          logoUrl: resolveLogoUrl(workspace?.avatar_url, DEFAULT_WORKSPACE_LOGO),
        })
      })
      .catch(() => {
        if (!cancelled) {
          setBranding({ name: fallbackName, tagline: '', logoUrl: DEFAULT_WORKSPACE_LOGO })
        }
      })
    return () => {
      cancelled = true
    }
  }, [fallbackName])

  return branding
}
