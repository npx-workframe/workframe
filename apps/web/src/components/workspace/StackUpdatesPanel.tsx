import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Download } from 'lucide-react'

import { OperationProgress, type OperationStep } from '@/components/ui/OperationProgress'
import { WfActionButton } from '@/components/ui/WfActionButton'
import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import {
  advanceUpdateSteps,
  completeUpdateSteps,
  initialUpdateSteps,
  isStackRestartError,
  stackUpdateTitle,
  waitForStackHealth,
  type StackUpdateTarget,
} from '@/lib/stackUpdateProgress'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi, type StackProductUpdateStatus, type StackUpdatesStatus } from '@/lib/workframeAuthApi'

type UpdateTarget = StackUpdateTarget

type StackUpdatesPanelProps = {
  onBadgeChange?: (count: number) => void
}

const APPLY_TIMEOUT_MS = 920_000

function readDesktopVersion(): Promise<string> {
  if (typeof window === 'undefined') return Promise.resolve('')
  const bridge = (window as Window & { workframe?: { getAppVersion?: () => Promise<string> } }).workframe
  if (!bridge?.getAppVersion) return Promise.resolve('')
  return bridge.getAppVersion().catch(() => '')
}

function resolveCanUpdate(product: StackProductUpdateStatus, dockerOk: boolean): boolean {
  if (product.can_update === true) return true
  if (product.can_update === false) return false
  return dockerOk && product.update_available
}

function formatVersionLabel(value: string): string {
  if (!value) return ''
  if (value === 'latest' || /^v/i.test(value)) return value
  return `v${value}`
}

function formatProductDetail(product: {
  current?: string
  latest?: string
  update_available: boolean
  package_pin?: string
  api_env?: string
  api_build?: string
  ui_build?: string
  install_drift?: boolean
}): string | undefined {
  const pin = product.package_pin?.trim() || product.current?.trim()
  if (!pin) return undefined
  const label = formatVersionLabel(pin)
  const mismatches: string[] = []
  const api = product.api_build?.trim() || product.api_env?.trim()
  const ui = product.ui_build?.trim()
  if (api && api !== pin) mismatches.push(`API ${formatVersionLabel(api)}`)
  if (ui && ui !== pin) mismatches.push(`UI ${formatVersionLabel(ui)}`)
  if (product.install_drift && mismatches.length > 0) {
    return `${label} · running ${mismatches.join(', ')}`
  }
  const latest = product.latest?.trim()
  if (product.update_available && latest && latest !== pin) {
    return `${label} · latest ${formatVersionLabel(latest)}`
  }
  return label
}

function formatHermesDetail(product: StackProductUpdateStatus): string | undefined {
  for (const raw of [product.agent_version, product.current]) {
    const version = raw?.trim()
    if (version && /^\d+\.\d+/.test(version)) {
      return formatVersionLabel(version)
    }
  }
  const imageTag = product.image_tag?.trim()
  return imageTag ? formatVersionLabel(imageTag) : undefined
}

type UpdateRowProps = {
  name: string
  detail?: string
  product: StackProductUpdateStatus
  actionLabel: string
  applying: boolean
  disabled: boolean
  dockerOk: boolean
  onApply: () => void
  downloadUrl?: string
}

function UpdateRow({
  name,
  detail,
  product,
  actionLabel,
  applying,
  disabled,
  dockerOk,
  onApply,
  downloadUrl,
}: UpdateRowProps) {
  const canUpdate = resolveCanUpdate(product, dockerOk)
  const upToDate = !product.update_available
  const blocked = product.update_available && !canUpdate

  return (
    <div className="wf-stack-updates__card">
      <div className="wf-stack-updates__card-main">
        <strong className="wf-stack-updates__card-title">{name}</strong>
        {detail ? <span className="wf-stack-updates__muted">{detail}</span> : null}
        {blocked || (product.install_drift && product.reason) ? (
          <span className="wf-stack-updates__reason">
            {product.reason || 'Update from the host — one-click apply is not available here.'}
          </span>
        ) : null}
      </div>
      <div className="wf-stack-updates__card-actions">
        {upToDate ? (
          <span className="wf-stack-updates__status">Up to date!</span>
        ) : (
          <>
            <span className="wf-stack-updates__status">{blocked ? 'Manual step' : 'Update available'}</span>
            {downloadUrl ? (
              <a
                href={downloadUrl}
                target="_blank"
                rel="noreferrer"
                className="wf-action-btn wf-stack-updates__btn"
                data-tone="primary"
              >
                <Download className="wf-stack-updates__action-icon" aria-hidden="true" />
                Download
              </a>
            ) : canUpdate ? (
              <WfActionButton
                type="button"
                tone="primary"
                className="wf-stack-updates__btn"
                disabled={disabled}
                onClick={onApply}
              >
                {applying ? 'Updating…' : actionLabel}
              </WfActionButton>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}

export function StackUpdatesPanel({ onBadgeChange }: StackUpdatesPanelProps) {
  const [status, setStatus] = useState<StackUpdatesStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState<UpdateTarget | ''>('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [updateSteps, setUpdateSteps] = useState<OperationStep[]>([])
  const [updateTarget, setUpdateTarget] = useState<UpdateTarget | ''>('')
  const waitAbortRef = useRef<AbortController | null>(null)

  const updating = updateSteps.length > 0
  const updateFailed = updateSteps.some((step) => step.status === 'error')

  const updateCount = useMemo(() => {
    if (!status) return 0
    const applyOk = status.update_apply_ready !== false && status.docker_available !== false
    let count = 0
    if (status.workframe?.update_available && resolveCanUpdate(status.workframe, applyOk)) count += 1
    if (status.hermes?.update_available && resolveCanUpdate(status.hermes, applyOk)) count += 1
    if (status.desktop?.update_available && status.desktop.download_url) count += 1
    return count
  }, [status])

  const canApplyAny = useMemo(() => {
    if (!status) return false
    const applyOk = status.update_apply_ready !== false && status.docker_available !== false
    return Boolean(
      (status.workframe.update_available && resolveCanUpdate(status.workframe, applyOk)) ||
        (status.hermes.update_available && resolveCanUpdate(status.hermes, applyOk)),
    )
  }, [status])

  const applyReady = status?.update_apply_ready !== false && status?.docker_available !== false
  const applyChannel = status?.update_apply_channel
  const applyBlockedMessage =
    status?.workframe?.reason ||
    status?.hermes?.reason ||
    (status?.supervisor_configured
      ? 'Stack updates are not ready — check that update scripts are installed and supervisor can reach Docker.'
      : 'In-place updates need workframe-supervisor or Docker on the stack host.')

  useEffect(() => {
    onBadgeChange?.(updateCount)
  }, [onBadgeChange, updateCount])

  useEffect(() => {
    return () => {
      waitAbortRef.current?.abort()
    }
  }, [])

  const load = useCallback(async () => {
    if (updating) return
    setLoading(true)
    setError('')
    try {
      const desktopVersion = await readDesktopVersion()
      const next = await workframeAuthApi.getAdminUpdates(desktopVersion || undefined)
      setStatus(next)
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Check updates'))
    } finally {
      setLoading(false)
    }
  }, [updating])

  useEffect(() => {
    void load()
  }, [load])

  const dismissUpdateProgress = useCallback(() => {
    waitAbortRef.current?.abort()
    setUpdateSteps([])
    setUpdateTarget('')
    setApplying('')
    void load()
  }, [load])

  const apply = async (target: UpdateTarget) => {
    waitAbortRef.current?.abort()
    const waitAbort = new AbortController()
    waitAbortRef.current = waitAbort

    setApplying(target)
    setUpdateTarget(target)
    setError('')
    setMessage('')
    setUpdateSteps(initialUpdateSteps(target))

    const advance = (stepId: string, detail?: string) => {
      setUpdateSteps((current) => advanceUpdateSteps(current, stepId, detail))
    }

    try {
      let applyAccepted = false
      try {
        const result = await workframeAuthApi.applyAdminUpdate(target, { timeoutMs: APPLY_TIMEOUT_MS })
        if (!result.ok) {
          throw new Error(result.error || 'Update failed')
        }
        applyAccepted = true
      } catch (err) {
        if (!isStackRestartError(err)) {
          throw err
        }
      }

      advance('rebuild', applyAccepted ? 'Update accepted' : 'Stack is restarting…')
      await new Promise((resolve) => window.setTimeout(resolve, 450))
      advance('health', 'Waiting for stack…')

      const healthy = await waitForStackHealth({
        signal: waitAbort.signal,
        onPoll: (attempt) => {
          setUpdateSteps((current) =>
            advanceUpdateSteps(
              current,
              'health',
              attempt === 1 ? 'Waiting for stack…' : `Still waiting… (${attempt})`,
            ),
          )
        },
      })

      if (!healthy) {
        throw new Error('request_timeout')
      }

      advance('refresh')
      setUpdateSteps((current) => completeUpdateSteps(current))
      await new Promise((resolve) => window.setTimeout(resolve, 500))
      window.location.reload()
    } catch (err) {
      const notice = formatWorkframeErrorMessage(err, 'Apply update')
      setError(notice)
      setUpdateSteps((current) =>
        current.map((entry) =>
          entry.status === 'active' ? { ...entry, status: 'error', detail: notice } : entry,
        ),
      )
    } finally {
      setApplying('')
    }
  }

  const dockerOk = applyReady
  const applyDisabled = !dockerOk || Boolean(applying) || updating

  return (
    <div className="wf-stack-updates space-y-3" role="tabpanel">
      {error && (!updating || updateFailed) ? <WorkframeNotice message={error} tone="neutral" /> : null}
      {message ? <WorkframeStatusNotice message={message} /> : null}
      {loading && !status && !updating ? <p className="wf-user-settings__hint">Checking for updates…</p> : null}

      {updating ? (
        <>
          <OperationProgress
            steps={updateSteps}
            title={updateTarget ? stackUpdateTitle(updateTarget) : 'Updating stack'}
            className="wf-stack-updates__progress"
          />
          {updateFailed ? (
            <WfActionButton type="button" className="wf-stack-updates__btn" onClick={dismissUpdateProgress}>
              Back to updates
            </WfActionButton>
          ) : null}
        </>
      ) : null}

      {status && !applyReady && !updating ? (
        <WorkframeNotice message={applyBlockedMessage} tone="neutral" />
      ) : null}

      {status && applyReady && applyChannel === 'supervisor' && !updating ? (
        <p className="wf-user-settings__hint">Updates apply via the stack supervisor (runtime data and configs are preserved).</p>
      ) : null}

      {status && !updating ? (
        <>
          <div className="wf-stack-updates__toolbar">
            <WfActionButton
              type="button"
              className="wf-stack-updates__btn"
              disabled={loading || Boolean(applying)}
              onClick={() => void load()}
            >
              {loading ? 'Checking…' : 'Check again'}
            </WfActionButton>
          </div>
          <UpdateRow
            name="Workframe"
            detail={formatProductDetail(status.workframe)}
            product={status.workframe}
            actionLabel={status.workframe.install_drift ? 'Repair' : 'Update'}
            applying={applying === 'workframe'}
            disabled={applyDisabled}
            dockerOk={dockerOk}
            onApply={() => void apply('workframe')}
          />

          <UpdateRow
            name="Hermes gateway"
            detail={formatHermesDetail(status.hermes)}
            product={status.hermes}
            actionLabel="Update"
            applying={applying === 'hermes'}
            disabled={applyDisabled}
            dockerOk={dockerOk}
            onApply={() => void apply('hermes')}
          />

          {status.desktop.current ? (
            <UpdateRow
              name="Desktop app"
              detail={formatProductDetail(status.desktop)}
              product={status.desktop}
              actionLabel="Download"
              applying={false}
              disabled={applyDisabled}
              dockerOk={dockerOk}
              onApply={() => {}}
              downloadUrl={
                status.desktop.update_available && status.desktop.download_url
                  ? status.desktop.download_url
                  : undefined
              }
            />
          ) : null}

          {updateCount > 1 && canApplyAny ? (
            <div className="flex justify-end pt-1">
              <WfActionButton
                type="button"
                tone="primary"
                className="wf-stack-updates__btn"
                disabled={applyDisabled}
                onClick={() => void apply('all')}
              >
                {applying === 'all' ? 'Updating…' : 'Update all'}
              </WfActionButton>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
