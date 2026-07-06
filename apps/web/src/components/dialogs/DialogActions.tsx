import type { ComponentProps } from 'react'

import { WfActionButton } from '@/components/ui/WfActionButton'
import { cn } from '@/lib/utils'

type DialogActionButtonProps = Omit<ComponentProps<typeof WfActionButton>, 'tone' | 'wizardSize'>

export function DialogCancelButton({ className, ...props }: DialogActionButtonProps) {
  return <WfActionButton type="button" wizardSize className={cn(className)} {...props} />
}

export function DialogConfirmButton({ className, ...props }: DialogActionButtonProps) {
  return (
    <WfActionButton type="button" tone="primary" wizardSize className={cn(className)} {...props} />
  )
}
