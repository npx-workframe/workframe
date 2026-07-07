import { forwardRef, type ComponentPropsWithoutRef } from 'react'

import { cn } from '@/lib/utils'

import '@/styles/scroll-area.css'

export const scrollAreaClass = 'wf-scroll'

export type ScrollAreaAxis = 'vertical' | 'horizontal' | 'both'
export type ScrollAreaInset = 'sm' | 'md' | 'rail'

type ScrollAreaProps = ComponentPropsWithoutRef<'div'> & {
  axis?: ScrollAreaAxis
  inset?: ScrollAreaInset
}

const axisClass: Record<ScrollAreaAxis, string> = {
  vertical: 'wf-scroll--vertical',
  horizontal: 'wf-scroll--horizontal',
  both: 'wf-scroll--both',
}

const insetClass: Record<ScrollAreaInset, string> = {
  sm: 'wf-scroll--inset-sm',
  md: 'wf-scroll--inset-md',
  rail: 'wf-scroll--inset-rail',
}

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ axis = 'both', inset, className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        scrollAreaClass,
        axisClass[axis],
        inset && insetClass[inset],
        axis !== 'horizontal' && 'wf-scroll-host',
        className,
      )}
      {...props}
    />
  ),
)
ScrollArea.displayName = 'ScrollArea'
