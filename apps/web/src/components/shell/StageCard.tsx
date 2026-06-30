import type { ReactNode } from 'react'

type StageCardProps = {
  eyebrow?: string
  title: string
  titleId?: string
  children: ReactNode
}

export function StageCard({ eyebrow, title, titleId, children }: StageCardProps) {
  return (
    <section className="wf-stage" aria-labelledby={titleId}>
      {eyebrow ? <p className="wf-stage__eyebrow">{eyebrow}</p> : null}
      <h1 className="wf-stage__title" id={titleId}>
        {title}
      </h1>
      <div className="wf-stage__content">{children}</div>
    </section>
  )
}
