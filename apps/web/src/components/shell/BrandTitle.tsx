type BrandTitleProps = {
  projectName: string
  subtitle?: string
}

export function BrandTitle({ projectName, subtitle = 'Workframe UI' }: BrandTitleProps) {
  return (
    <div className="wf-brand__copy">
      <span className="wf-brand__title">{projectName}</span>
      <span className="wf-brand__subtitle">{subtitle}</span>
    </div>
  )
}
