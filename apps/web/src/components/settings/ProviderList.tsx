import type { ReactNode } from 'react'

type ProviderListProps = {
  title: string
  children: ReactNode
}

export function ProviderList({ title, children }: ProviderListProps) {
  return (
    <div className="wf-provider-connect__group">
      <h4 className="wf-provider-connect__group-title">{title}</h4>
      <ul className="wf-provider-connect__list">{children}</ul>
    </div>
  )
}
