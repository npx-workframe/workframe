import type { ReactNode } from 'react'

type ModelListGroupProps = {
  provider: string
  children: ReactNode
}

export function ModelListGroup({ provider, children }: ModelListGroupProps) {
  return (
    <div className="wf-dialog__group">
      <p className="wf-dialog__group-label">{provider}</p>
      {children}
    </div>
  )
}
