import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type PanelShellProps = {
  children: ReactNode
  className?: string
}

export function PanelShell({ children, className }: PanelShellProps) {
  return <div className={cn('wf-panel', className)}>{children}</div>
}
