import { cn } from '@/lib/utils'

type DividerProps = {
  className?: string
}

export function Divider({ className }: DividerProps) {
  return <hr className={cn('wf-divider', className)} aria-hidden="true" />
}
