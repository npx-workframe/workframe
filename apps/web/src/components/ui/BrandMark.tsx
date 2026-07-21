import { useState } from 'react'

import { providerIconForId } from '@/lib/brandAssets'
import { cn } from '@/lib/utils'

type BrandMarkProps = {
  providerId?: string
  src?: string | null
  label?: string
  className?: string
  themeAware?: boolean
}

/** One resilient rendering rule for third-party marks across themes. */
export function BrandMark({
  providerId = '',
  src,
  label = '',
  className,
  themeAware = true,
}: BrandMarkProps) {
  const resolvedSrc = src === undefined ? providerIconForId(providerId) : src
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const classes = cn('wf-brand-mark', themeAware && 'wf-brand-img--theme', className)
  const fallback = (label || providerId || '?').trim().slice(0, 1).toUpperCase() || '?'

  if (!resolvedSrc || failedSrc === resolvedSrc) {
    return (
      <span
        className={cn(classes, 'wf-brand-mark--fallback')}
        role={label ? 'img' : undefined}
        aria-label={label || undefined}
        aria-hidden={label ? undefined : true}
      >
        {fallback}
      </span>
    )
  }

  return (
    <img
      src={resolvedSrc}
      alt={label}
      className={classes}
      aria-hidden={label ? undefined : true}
      onError={() => setFailedSrc(resolvedSrc)}
    />
  )
}
