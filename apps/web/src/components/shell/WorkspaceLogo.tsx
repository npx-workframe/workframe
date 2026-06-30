import { useEffect, useState } from 'react'

import { resolveLogoUrl } from '@/lib/avatarResolve'
import { DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import { cn } from '@/lib/utils'

type WorkspaceLogoProps = {
  src?: string
  alt?: string
  className?: string
}

export function WorkspaceLogo({
  src,
  alt = 'Workframe',
  className,
}: WorkspaceLogoProps) {
  const [logoSrc, setLogoSrc] = useState(src ?? DEFAULT_WORKSPACE_LOGO)

  useEffect(() => {
    if (src) {
      setLogoSrc(resolveLogoUrl(src, DEFAULT_WORKSPACE_LOGO))
      return
    }
    let cancelled = false
    void workframeAuthApi
      .getMe()
      .then((me) => {
        if (cancelled) return
        const workspace = me.current_workspace ?? me.default_workspace
        setLogoSrc(resolveLogoUrl(workspace?.avatar_url, DEFAULT_WORKSPACE_LOGO))
      })
      .catch(() => {
        if (!cancelled) setLogoSrc(DEFAULT_WORKSPACE_LOGO)
      })
    return () => {
      cancelled = true
    }
  }, [src])

  return (
    <img
      src={logoSrc}
      alt={alt}
      className={cn('wf-workspace-logo', className)}
      loading="lazy"
      decoding="async"
    />
  )
}
