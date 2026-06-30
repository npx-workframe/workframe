import type { ReactNode } from 'react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

function dialogBodyScrolls(contentClassName?: string, hasFooter?: boolean) {
  if (hasFooter) return true
  if (!contentClassName) return false
  return (
    contentClassName.includes('wf-auth-dialog') ||
    contentClassName.includes('wf-dialog-content--create-agent')
  )
}

type DialogFrameProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children?: ReactNode
  footer?: ReactNode
  showClose?: boolean
  contentClassName?: string
  modal?: boolean
}

export function DialogFrame({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  showClose = true,
  contentClassName,
  modal = true,
}: DialogFrameProps) {
  const hasFooter = Boolean(footer)
  const scrollBody = dialogBodyScrolls(contentClassName, hasFooter)

  return (
    <Dialog open={open} onOpenChange={onOpenChange} modal={modal}>
      <DialogContent
        showClose={showClose}
        className={cn(contentClassName, hasFooter && 'wf-dialog-content--has-footer')}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        {children ? (
          <div
            className={cn(
              'wf-dialog-body',
              scrollBody && 'wf-scroll wf-scroll--vertical wf-scroll-host',
            )}
          >
            {children}
          </div>
        ) : null}
        {hasFooter ? <DialogFooter>{footer}</DialogFooter> : null}
      </DialogContent>
    </Dialog>
  )
}
