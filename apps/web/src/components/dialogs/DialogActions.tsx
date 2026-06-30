import type { ComponentProps } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type DialogActionButtonProps = ComponentProps<typeof Button>

export function DialogCancelButton({ className, ...props }: DialogActionButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      size="dialog"
      className={cn('wf-dialog-btn', className)}
      {...props}
    />
  )
}

export function DialogConfirmButton({
  className,
  variant = 'accent',
  ...props
}: DialogActionButtonProps) {
  return (
    <Button
      type="button"
      variant={variant}
      size="dialog"
      className={cn('wf-dialog-btn', className)}
      {...props}
    />
  )
}
