import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi, type StackProductUpdateStatus, type StackUpdatesStatus } from '@/lib/workframeAuthApi'

type UpdateTarget = 'hermes' | 'workframe' | 'all'

type StackUpdatesPanelProps = {
  onBadgeChange?: (count: number) => void
}

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

function formatProductDetail(product: { current?: string; latest?: string; update_available: boolean }): string | undefined {
  const current = product.current?.trim()
  if (!current) return undefined
  const label = formatVersionLabel(current)
  const latest = product.latest?.trim()
  if (product.update_available && latest && latest !== current) {
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
        {blocked ? (
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
              <Button type="button" size="sm" variant="default" asChild>
                <a href={downloadUrl} target="_blank" rel="noreferrer">
                  <Download className="wf-stack-updates__action-icon" aria-hidden="true" />
                  Download
                </a>
              </Button>
            ) : canUpdate ? (
              <Button type="button" size="sm" variant="default" disabled={disabled} onClick={onApply}>
                {applying ? 'Updating…' : actionLabel}
              </Button>
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

  const updateCount = useMemo(() => {
    if (!status) return 0
    let count = 0
    if (status.workframe?.update_available) count += 1
    if (status.hermes?.update_available) count += 1
    if (status.desktop?.update_available) count += 1
    return count
  }, [status])

  const canApplyAny = useMemo(() => {
    if (!status) return false
    const dockerOk = status.docker_available !== false
    return Boolean(
      (status.workframe.update_available && resolveCanUpdate(status.workframe, dockerOk)) ||
        (status.hermes.update_available && resolveCanUpdate(status.hermes, dockerOk)),
    )
  }, [status])

  useEffect(() => {
    onBadgeChange?.(updateCount)
  }, [onBadgeChange, updateCount])

  const load = useCallback(async () => {
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
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const apply = async (target: UpdateTarget) => {
    setApplying(target)
    setError('')
    setMessage('')
    try {
      const result = await workframeAuthApi.applyAdminUpdate(target)
      if (!result.ok) {
        throw new Error(result.error || 'Update failed')
      }
      setMessage(target === 'hermes' ? 'Hermes updated.' : target === 'workframe' ? 'Workframe updated.' : 'Stack updated.')
      await load()
      if (target === 'hermes' || target === 'all') {
        await new Promise((r) => setTimeout(r, 1500))
        await load()
      }
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Apply update'))
    } finally {
      setApplying('')
    }
  }

  const dockerOk = status?.docker_available !== false
  const applyDisabled = !dockerOk || Boolean(applying)

  return (
    <div className="wf-stack-updates space-y-3" role="tabpanel">
      {error ? <WorkframeNotice message={error} tone="neutral" /> : null}
      {message ? <WorkframeStatusNotice message={message} /> : null}
      {loading && !status ? <p className="wf-user-settings__hint">Checking for updates…</p> : null}

      {!dockerOk ? (
        <WorkframeNotice message="Docker is not available to the API — in-place updates need a Docker host." tone="neutral" />
      ) : null}

      {status ? (
        <>
          <UpdateRow
            name="Workframe"
            detail={formatProductDetail(status.workframe)}
            product={status.workframe}
            actionLabel="Update"
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
              <Button type="button" variant="default" disabled={applyDisabled} onClick={() => void apply('all')}>
                {applying === 'all' ? 'Updating…' : 'Update all'}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
