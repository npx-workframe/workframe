import type { OperationStep } from '@/components/ui/OperationProgress'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

export type StackUpdateTarget = 'hermes' | 'workframe' | 'all'

const RESTART_ERROR_RE =
  /upstream service unavailable|service temporarily unavailable|failed to fetch|networkerror|load failed|http_502|http_503|\b502\b|\b503\b|request_timeout|aborted|network request failed|remote end closed|connection reset|supervisor_apply_failed:remote end closed/i

export function stackUpdateStepLabels(target: StackUpdateTarget): Array<{ id: string; label: string }> {
  const rebuild =
    target === 'hermes'
      ? 'Rebuild Hermes gateway'
      : target === 'workframe'
        ? 'Rebuild Workframe stack'
        : 'Rebuild stack services'
  return [
    { id: 'apply', label: 'Apply update' },
    { id: 'rebuild', label: rebuild },
    { id: 'health', label: 'Wait for stack to come back' },
    { id: 'refresh', label: 'Reload Workframe' },
  ]
}

export function stackUpdateTitle(target: StackUpdateTarget): string {
  if (target === 'hermes') return 'Updating Hermes gateway'
  if (target === 'workframe') return 'Updating Workframe'
  return 'Updating stack'
}

export function initialUpdateSteps(target: StackUpdateTarget): OperationStep[] {
  return stackUpdateStepLabels(target).map((entry, index) => ({
    ...entry,
    status: index === 0 ? 'active' : 'pending',
  }))
}

export function advanceUpdateSteps(
  steps: OperationStep[],
  nextActiveId: string,
  detail?: string,
): OperationStep[] {
  const nextIndex = steps.findIndex((step) => step.id === nextActiveId)
  if (nextIndex < 0) return steps
  return steps.map((entry, index) => {
    if (index < nextIndex) return { ...entry, status: 'done' as const }
    if (entry.id === nextActiveId) return { ...entry, status: 'active' as const, detail }
    return { ...entry, status: 'pending' as const }
  })
}

export function completeUpdateSteps(steps: OperationStep[]): OperationStep[] {
  return steps.map((entry) => ({ ...entry, status: 'done' as const }))
}

/** Expected while containers restart during a supervisor-driven apply. */
export function isStackRestartError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err ?? '')
  return RESTART_ERROR_RE.test(message)
}

export async function waitForStackHealth(options?: {
  intervalMs?: number
  maxWaitMs?: number
  onPoll?: (attempt: number) => void
  signal?: AbortSignal
}): Promise<boolean> {
  const intervalMs = options?.intervalMs ?? 2000
  const maxWaitMs = options?.maxWaitMs ?? 15 * 60 * 1000
  const started = Date.now()
  let attempt = 0

  while (Date.now() - started < maxWaitMs) {
    if (options?.signal?.aborted) return false
    attempt += 1
    options?.onPoll?.(attempt)
    try {
      const health = await workframeAuthApi.getApiHealth()
      if (health?.ok) return true
    } catch {
      // Stack is still restarting.
    }
    await new Promise<void>((resolve) => {
      const timer = window.setTimeout(resolve, intervalMs)
      options?.signal?.addEventListener(
        'abort',
        () => {
          window.clearTimeout(timer)
          resolve()
        },
        { once: true },
      )
    })
  }

  return false
}
