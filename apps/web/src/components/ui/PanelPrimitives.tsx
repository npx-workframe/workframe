import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Muted status line — loading, waiting, empty states inside panels. */
export function PanelStatus({
  children,
  className,
  role = 'status',
}: {
  children: ReactNode
  className?: string
  role?: 'status' | 'alert'
}) {
  return (
    <p className={cn('wf-panel-status', className)} role={role}>
      {children}
    </p>
  )
}

/** Inline notice inside wizard / OTP / settings panels — matches auth OTP notice chrome. */
export function PanelInlineNotice({
  children,
  tone = 'error',
  className,
}: {
  children: ReactNode
  tone?: 'error' | 'info'
  className?: string
}) {
  return (
    <div
      className={cn(
        'wf-auth-otp-panel__notice',
        tone === 'error' && 'wf-auth__alert--error',
        tone === 'info' && 'wf-auth__alert--info',
        className,
      )}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  )
}

/** Footer action row for embedded panels (matches dialog / settings shell footers). */
export function PanelFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('wf-panel-footer', className)}>{children}</div>
}

/** Empty list placeholder inside settings / member grids — existing dashed-border chrome. */
export function PanelEmptyState({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn('wf-user-settings__hint text-center p-8 border border-dashed border-border rounded-xl', className)}>
      {children}
    </p>
  )
}
