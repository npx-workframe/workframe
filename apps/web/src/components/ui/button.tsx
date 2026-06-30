import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from '@radix-ui/react-slot'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        outline:
          'border border-border bg-background/60 text-foreground hover:bg-accent hover:text-accent-foreground',
        ghost: 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
        toolbar: 'wf-tool-btn shadow-none',
        destructive:
          'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        accent:
          'border border-border bg-background/50 text-foreground hover:bg-[var(--wf-dialog-accent-hover-bg)] hover:text-[var(--wf-dialog-accent-hover-text)] hover:border-[var(--wf-dialog-accent-hover-border)]',
        warn:
          'border border-border bg-background/50 text-foreground hover:bg-[var(--wf-dialog-warn-hover-bg)] hover:text-[var(--wf-dialog-warn-hover-text)] hover:border-[var(--wf-dialog-warn-hover-border)]',
      },
      size: {
        default: 'h-8 px-3 py-1.5',
        sm: 'h-7 rounded-md px-2.5 text-xs',
        dialog: 'h-7 min-w-[4.5rem] rounded-md px-2.5 text-xs font-medium',
        icon: 'h-8 w-8',
        toolbarIcon: 'wf-tool-btn--icon h-auto w-auto min-h-0 p-0',
        toolbarText: 'wf-tool-btn--text h-auto min-h-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
