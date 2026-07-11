import type { ReactNode } from 'react'

import { PanelEmptyState } from '@/components/ui/PanelPrimitives'
import { cn } from '@/lib/utils'

type ProfileEntityCardGridProps = {
  children: ReactNode
  className?: string
}

export function ProfileEntityCardGrid({ children, className }: ProfileEntityCardGridProps) {
  return <div className={cn('grid grid-cols-1 md:grid-cols-2 gap-3', className)}>{children}</div>
}

type ProfileEntityCardRowProps = {
  children: ReactNode
  action?: ReactNode
}

/** Profile card with optional hover action overlay — workframe / project member lists. */
export function ProfileEntityCardRow({ children, action }: ProfileEntityCardRowProps) {
  return (
    <div className="relative group">
      {children}
      {action ? (
        <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
          {action}
        </div>
      ) : null}
    </div>
  )
}

type ProfileEntityCardGridOrEmptyProps = ProfileEntityCardGridProps & {
  isEmpty: boolean
  emptyMessage?: string
}

export function ProfileEntityCardGridOrEmpty({
  isEmpty,
  emptyMessage,
  children,
  className,
}: ProfileEntityCardGridOrEmptyProps) {
  if (isEmpty && emptyMessage) {
    return <PanelEmptyState>{emptyMessage}</PanelEmptyState>
  }
  return <ProfileEntityCardGrid className={className}>{children}</ProfileEntityCardGrid>
}
