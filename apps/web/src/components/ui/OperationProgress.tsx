import { Check, Loader2, X } from 'lucide-react'

import { cn } from '@/lib/utils'

export type OperationStep = {
  id: string
  label: string
  status: 'pending' | 'active' | 'done' | 'error'
  detail?: string
}

type OperationProgressProps = {
  steps: OperationStep[]
  title?: string
  className?: string
}

export function OperationProgress({ steps, title, className }: OperationProgressProps) {
  if (!steps.length) return null

  const done = steps.filter((step) => step.status === 'done').length
  const progress = Math.round((done / steps.length) * 100)

  return (
    <div className={cn('wf-operation-progress', className)} aria-live="polite">
      {title ? <p className="wf-operation-progress__title">{title}</p> : null}
      <div
        className="wf-onboarding-wizard__progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
      >
        <div className="wf-onboarding-wizard__progress-bar" style={{ width: `${progress}%` }} />
      </div>
      <ol className="wf-operation-progress__list">
        {steps.map((step) => (
          <li
            key={step.id}
            className={cn(
              'wf-operation-progress__item',
              step.status === 'active' && 'wf-operation-progress__item--active',
              step.status === 'done' && 'wf-operation-progress__item--done',
              step.status === 'error' && 'wf-operation-progress__item--error',
            )}
          >
            <span className="wf-operation-progress__icon" aria-hidden>
              {step.status === 'done' ? <Check /> : null}
              {step.status === 'active' ? <Loader2 className="wf-spin" /> : null}
              {step.status === 'error' ? <X /> : null}
            </span>
            <span className="wf-operation-progress__label">{step.label}</span>
            {step.detail ? <span className="wf-operation-progress__detail">{step.detail}</span> : null}
          </li>
        ))}
      </ol>
    </div>
  )
}

export function stepsFromApiResults(
  labels: Array<{ id: string; label: string }>,
  apiSteps: Array<{ step?: string; ok?: boolean; error?: string }> | undefined,
  activeIndex: number,
): OperationStep[] {
  const byId = new Map((apiSteps ?? []).map((row) => [String(row.step || ''), row]))
  return labels.map((entry, index) => {
    const row = byId.get(entry.id)
    if (row?.ok === false) {
      return { ...entry, status: 'error' as const, detail: String(row.error || 'Failed') }
    }
    if (row?.ok === true) {
      return { ...entry, status: 'done' as const }
    }
    if (index === activeIndex) return { ...entry, status: 'active' as const }
    if (index < activeIndex) return { ...entry, status: 'done' as const }
    return { ...entry, status: 'pending' as const }
  })
}

export async function animateOperationSteps(
  labels: Array<{ id: string; label: string }>,
  onUpdate: (steps: OperationStep[]) => void,
  run: () => Promise<Array<{ step?: string; ok?: boolean; error?: string }> | undefined>,
) {
  const pending = labels.map((entry) => ({ ...entry, status: 'pending' as const }))
  onUpdate(pending)
  for (let index = 0; index < labels.length; index++) {
    onUpdate(
      labels.map((entry, i) => ({
        ...entry,
        status: i < index ? 'done' : i === index ? 'active' : 'pending',
      })),
    )
    await new Promise((resolve) => window.setTimeout(resolve, 280))
  }
  let apiSteps: Array<{ step?: string; ok?: boolean; error?: string }> | undefined
  try {
    apiSteps = await run()
  } catch (err) {
    onUpdate(
      labels.map((entry, i) => ({
        ...entry,
        status: i === labels.length - 1 ? 'error' : i < labels.length - 1 ? 'done' : 'pending',
        detail: err instanceof Error ? err.message : 'Failed',
      })),
    )
    throw err
  }
  onUpdate(stepsFromApiResults(labels, apiSteps, labels.length))
  return apiSteps
}
