type MoleskineGridProps = {
  className?: string
}

/** Standalone moleskine line grid — theme tokens: --wf-moleskine-grid-tile, --wf-moleskine-grid-line. */
export function MoleskineGrid({ className }: MoleskineGridProps) {
  return (
    <div className={className ? `wf-moleskine-grid ${className}` : 'wf-moleskine-grid'} aria-hidden="true" />
  )
}
