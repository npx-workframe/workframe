type BrandMarkProps = {
  className?: string
}

export function BrandMark({ className }: BrandMarkProps) {
  return (
    <span
      className={['wf-brand__mark', className].filter(Boolean).join(' ')}
      aria-hidden="true"
    />
  )
}
