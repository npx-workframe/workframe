import { useCallback, useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { workframeAuthApi, type InstallStatus } from '@/lib/workframeAuthApi'

type InstallShellProps = {
  projectName: string
  onReady: () => void
}

const PHASE_LABELS: Record<string, string> = {
  hermes: 'Setting up Hermes…',
  workspace: 'Preparing workspace…',
  ready: 'Almost there…',
}

export function InstallShell({ projectName, onReady }: InstallShellProps) {
  const [status, setStatus] = useState<InstallStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(8)

  const poll = useCallback(async () => {
    try {
      const next = await workframeAuthApi.getInstallStatus()
      setStatus(next)
      setError(null)
      if (next.phase === 'ready' && next.setup_complete && next.hermes_present) {
        setProgress(100)
        window.setTimeout(onReady, 400)
        return true
      }
      setProgress((p) => Math.min(p + 6, 92))
      return false
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Install check failed')
      return false
    }
  }, [onReady])

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      const done = await poll()
      if (!cancelled && !done) {
        window.setTimeout(tick, 2000)
      }
    }
    void tick()
    return () => {
      cancelled = true
    }
  }, [poll])

  const phaseLabel = status ? PHASE_LABELS[status.phase] || 'Starting…' : 'Starting…'

  return (
    <DialogFrame
      open
      onOpenChange={() => {}}
      title={`Setting up ${projectName}`}
      description="Hi there — I'm getting your Workframe ready."
      showClose={false}
      contentClassName="wf-auth-dialog"
    >
      <p className="wf-auth__status">{phaseLabel}</p>
      <div className="wf-install-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
        <div className="wf-install-progress__bar" style={{ width: `${progress}%` }} />
      </div>
      {error ? <p className="wf-auth__alert wf-auth__alert--info">{error} — retrying…</p> : null}
      {status?.hermes_present === false ? (
        <p className="text-sm text-muted-foreground">Bootstrapping agent profiles in the background.</p>
      ) : null}
    </DialogFrame>
  )
}
