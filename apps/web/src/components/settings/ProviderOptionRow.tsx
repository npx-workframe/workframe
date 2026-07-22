import { WfActionButton } from '@/components/ui/WfActionButton'
import { SecretInput } from '@/components/ui/SecretInput'
import { Label } from '@/components/ui/label'
import { BrandMark } from '@/components/ui/BrandMark'
import type { ProviderConnectRow } from '@/lib/workframeAuthApi'

type ProviderOptionRowProps = {
  row: ProviderConnectRow
  disabled?: boolean
  isBusy?: boolean
  isExpanded?: boolean
  secretDraft?: string
  draftExtraSecrets?: Record<string, string>
  oauthOutput?: string
  onToggle: (nextOn: boolean) => void
  onSecretChange: (value: string) => void
  onExtraSecretChange: (envVar: string, value: string) => void
  onCancel: () => void
  onSave: () => void
  onOAuth?: () => void
  lockSharedCredential?: boolean
}

export function ProviderOptionRow({
  row,
  disabled,
  isBusy,
  isExpanded,
  secretDraft = '',
  draftExtraSecrets = {},
  oauthOutput,
  onToggle,
  onSecretChange,
  onExtraSecretChange,
  onCancel,
  onSave,
  onOAuth,
  lockSharedCredential,
}: ProviderOptionRowProps) {
  const inputType = row.connect_mode === 'bot_token' ? 'bot token' : 'API key'
  const showPatFallback = row.id === 'github' && row.connect_mode === 'oauth'
  return (
    <li className="wf-provider-connect__item">
      <div className="wf-provider-connect__row">
        <div className="wf-sign-in-app__icon" aria-hidden="true">
          <BrandMark providerId={row.id} className="wf-sign-in-app__brand-img" />
        </div>
        <div className="wf-provider-connect__copy">
          <div className="wf-provider-connect__title-row">
            <strong>{row.label}</strong>
            <code className="wf-provider-connect__env">{row.env_var || 'OAuth'}</code>
            {row.user_only ? <span className="wf-provider-connect__badge">per-user</span> : null}
            {row.source === 'workspace' ? <span className="wf-provider-connect__badge">shared</span> : null}
          </div>
          <span className="wf-provider-connect__desc">{row.description}</span>
        </div>
        <label className="wf-provider-connect__switch">
          <input
            type="checkbox"
            checked={row.connected}
            disabled={disabled || isBusy || (lockSharedCredential && row.source === 'workspace')}
            aria-label={`Connect ${row.label}`}
            onChange={(event) => onToggle(event.target.checked)}
          />
          <span className="wf-provider-connect__switch-ui" aria-hidden="true" />
        </label>
      </div>

      {isExpanded && (row.connect_mode !== 'oauth' || showPatFallback) ? (
        <div className="wf-provider-connect__editor">
          <div className="wf-dialog-field">
            <Label htmlFor={`wf-provider-secret-${row.id}`}>
              {showPatFallback ? 'GitHub personal access token' : inputType}
            </Label>
            {showPatFallback && row.oauth_configured === false ? (
              <p className="wf-dialog-field__hint">
                Fine-grained PAT works on its own — a workframe OAuth app is only needed for one-click GitHub connect.
              </p>
            ) : null}
            <SecretInput
              id={`wf-provider-secret-${row.id}`}
              value={secretDraft}
              onChange={(event) => onSecretChange(event.target.value)}
              saved={row.connected && !secretDraft}
              emptyPlaceholder={showPatFallback ? 'Paste personal access token' : `Paste ${inputType}`}
            />
          </div>
          {(row.extra_env_vars ?? []).map((extraVar) => (
            <div key={extraVar} className="wf-dialog-field">
              <Label htmlFor={`wf-provider-extra-${row.id}-${extraVar}`}>{extraVar}</Label>
              <SecretInput
                id={`wf-provider-extra-${row.id}-${extraVar}`}
                value={draftExtraSecrets[extraVar] ?? ''}
                onChange={(event) => onExtraSecretChange(extraVar, event.target.value)}
                saved={row.connected && !(draftExtraSecrets[extraVar] ?? '').trim()}
                emptyPlaceholder={`Paste ${extraVar}`}
              />
            </div>
          ))}
          <div className="wf-provider-connect__editor-actions">
            <WfActionButton wizardSize onClick={onCancel}>
              Cancel
            </WfActionButton>
            {showPatFallback && row.oauth_configured && onOAuth ? (
              <WfActionButton wizardSize disabled={isBusy} onClick={onOAuth}>
                OAuth instead
              </WfActionButton>
            ) : null}
            <WfActionButton wizardSize tone="primary" disabled={isBusy || !secretDraft.trim()} onClick={onSave}>
              {isBusy ? 'Saving…' : 'Save'}
            </WfActionButton>
          </div>
        </div>
      ) : null}

      {oauthOutput ? (
        <pre className="wf-provider-connect__oauth-output wf-scroll wf-scroll--vertical">{oauthOutput}</pre>
      ) : null}
    </li>
  )
}
