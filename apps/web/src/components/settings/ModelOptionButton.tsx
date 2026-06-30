import { providerIconForId } from '@/lib/workframeAssets'
import { cn } from '@/lib/utils'

type ModelOptionButtonProps = {
  label: string
  model: string
  provider?: string
  description?: string
  isCurrent?: boolean
  isPending?: boolean
  disabled?: boolean
  /** One row — label only, no description block. */
  singleLine?: boolean
  onSelect: () => void
}

export function ModelOptionButton({
  label,
  model,
  provider,
  description,
  isCurrent,
  isPending,
  disabled,
  singleLine,
  onSelect,
}: ModelOptionButtonProps) {
  const title = label.trim() || model
  const icon = provider ? providerIconForId(provider) : null

  return (
    <button
      type="button"
      className={cn('wf-dialog__option', singleLine && 'wf-dialog__option--single-line', isCurrent && 'is-current')}
      onClick={onSelect}
      disabled={disabled}
      data-current={isCurrent ? 'true' : undefined}
      title={singleLine ? model : undefined}
    >
      {icon ? (
        <img src={icon} alt="" className="wf-dialog__option-icon" aria-hidden="true" />
      ) : null}
      <span className="wf-dialog__option-label">{title}</span>
      {!singleLine && description ? <span className="wf-dialog__option-desc">{description}</span> : null}
      {isCurrent ? <span className="wf-dialog__option-tag">active</span> : null}
      {isPending ? <span className="wf-dialog__option-tag">saving…</span> : null}
    </button>
  )
}
