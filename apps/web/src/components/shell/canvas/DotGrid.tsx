type DotGridProps = {
  className?: string
}

/** Standalone dot texture layer — ink from theme tokens on html. */
export function DotGrid({ className }: DotGridProps) {
  return <div className={className ? `wf-dot-grid ${className}` : 'wf-dot-grid'} aria-hidden="true" />
}
