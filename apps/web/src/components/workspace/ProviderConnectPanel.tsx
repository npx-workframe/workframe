import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { ProviderList } from '@/components/settings/ProviderList'
import { ProviderOptionRow } from '@/components/settings/ProviderOptionRow'
import { PanelStatus } from '@/components/ui/PanelPrimitives'
import {
  DeviceCodeOAuthFlow,
  type DeviceCodeOAuthPresentation,
} from '@/components/integrations/DeviceCodeOAuthFlow'
import type { ProviderConnectRow } from '@/lib/workframeAuthApi'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import { isDeviceOAuthProvider } from '@/lib/providerOAuth'
import { clearProviderConnectReturn, peekProviderConnectReturn } from '@/lib/providerConnectReturn'

export const PROVIDER_CATEGORY_LABELS: Record<string, string> = {
  llm: 'LLM integrations',
  search: 'Search integrations',
  messaging: 'Messaging integrations',
  dev: 'Developer integrations',
  payments: 'Payment integrations',
}

type ProviderConnectPanelProps = {
  disabled?: boolean
  workspaceId?: string
  credentialScope?: 'user' | 'workspace'
  categories?: string[]
  providerIds?: string[]
  /** Top banner: none (default in wizard), compact (one line), full (boxed). */
  hint?: 'none' | 'compact' | 'full'
  /** stack = all categories; tabs = one category at a time. */
  layout?: 'stack' | 'tabs'
  /** When false, panel scroll is delegated to parent (wizard body). */
  scrollInner?: boolean
  /** Device-code OAuth: use inline inside an existing settings sheet; dialog on standalone surfaces. */
  deviceOAuthPresentation?: DeviceCodeOAuthPresentation
  onStatus?: (message: string) => void
  onError?: (message: string) => void
  onConnected?: () => void
}

export function ProviderConnectPanel({
  disabled,
  workspaceId,
  credentialScope = 'user',
  categories,
  providerIds,
  hint = 'full',
  layout = 'stack',
  scrollInner = true,
  deviceOAuthPresentation = 'dialog',
  onStatus,
  onError,
  onConnected,
}: ProviderConnectPanelProps) {
  const [providers, setProviders] = useState<ProviderConnectRow[]>([])
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [draftSecrets, setDraftSecrets] = useState<Record<string, string>>({})
  const [draftExtraSecrets, setDraftExtraSecrets] = useState<Record<string, Record<string, string>>>({})
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [oauthOutput, setOauthOutput] = useState<Record<string, string>>({})
  const [deviceOAuthRow, setDeviceOAuthRow] = useState<ProviderConnectRow | null>(null)
  const [activeCategory, setActiveCategory] = useState('')
  const deviceOAuthRowRef = useRef<ProviderConnectRow | null>(null)
  const onErrorRef = useRef(onError)
  const onStatusRef = useRef(onStatus)
  const onConnectedRef = useRef(onConnected)
  deviceOAuthRowRef.current = deviceOAuthRow
  onErrorRef.current = onError
  onStatusRef.current = onStatus
  onConnectedRef.current = onConnected

  const loadProviders = useCallback(async () => {
    setLoading(true)
    try {
      const result = await workframeAuthApi.listProviders(
        workspaceId,
        credentialScope === 'workspace' ? 'workspace' : 'effective',
      )
      setProviders(result.providers ?? [])
    } catch (err) {
      onErrorRef.current?.(err instanceof Error ? err.message : 'Failed to load integrations')
    } finally {
      setLoading(false)
    }
  }, [credentialScope, workspaceId])

  useEffect(() => {
    void loadProviders()
  }, [loadProviders])

  useEffect(() => {
    const returned = peekProviderConnectReturn()
    if (!returned) return
    if (returned.status === 'ok') {
      onStatusRef.current?.(returned.message)
      void loadProviders()
      onConnectedRef.current?.()
    } else {
      onErrorRef.current?.(returned.message)
    }
    clearProviderConnectReturn()
  }, [loadProviders])

  const grouped = useMemo(() => {
    const map = new Map<string, ProviderConnectRow[]>()
    const allowCat = categories?.length ? new Set(categories) : null
    const allowId = providerIds?.length ? new Set(providerIds) : null
    for (const row of providers) {
      if (credentialScope === 'workspace' && (row.user_only || row.connect_mode === 'oauth')) continue
      if (allowCat && !allowCat.has(row.category)) continue
      if (allowId && !allowId.has(row.id)) continue
      const bucket = map.get(row.category) ?? []
      bucket.push(row)
      map.set(row.category, bucket)
    }
    return [...map.entries()]
  }, [categories, credentialScope, providerIds, providers])

  useEffect(() => {
    if (!grouped.length) return
    setActiveCategory((current) =>
      current && grouped.some(([cat]) => cat === current) ? current : grouped[0][0],
    )
  }, [grouped])

  const refreshRow = (providerId: string, patch: Partial<ProviderConnectRow>) => {
    setProviders((current) =>
      current.map((row) => (row.id === providerId ? { ...row, ...patch } : row)),
    )
  }

  const disconnect = async (row: ProviderConnectRow) => {
    setBusyId(row.id)
    onError?.('')
    try {
      if (credentialScope === 'workspace' && row.credential_id && workspaceId) {
        await workframeAuthApi.revokeWorkspaceCredential(workspaceId, row.credential_id)
      } else if (row.credential_id) {
        await workframeAuthApi.disconnectCredential(row.credential_id)
      } else {
        await workframeAuthApi.disconnectProvider(row.id)
      }
      refreshRow(row.id, { connected: false, credential_id: null })
      setExpandedId((current) => (current === row.id ? null : current))
      setDraftSecrets((current) => {
        const next = { ...current }
        delete next[row.id]
        return next
      })
      onStatus?.(`Disconnected ${row.label}.`)
    } catch (err) {
      onError?.(err instanceof Error ? err.message : `Failed to disconnect ${row.label}`)
    } finally {
      setBusyId(null)
    }
  }

  const saveSecret = async (row: ProviderConnectRow) => {
    const secret = (draftSecrets[row.id] ?? '').trim()
    if (!secret) {
      onError?.(`Enter a ${row.connect_mode === 'bot_token' ? 'bot token' : 'API key'} for ${row.label}.`)
      return
    }
    setBusyId(row.id)
    onError?.('')
    try {
      if (credentialScope === 'workspace') {
        const wsId = workspaceId?.trim()
        if (!wsId) {
          onError?.('Workspace ID is required for shared keys.')
          return
        }
        const saved = await workframeAuthApi.storeWorkspaceCredential(wsId, {
          provider: row.id,
          api_key: secret,
          label: row.label,
        })
        if (!saved.ok) {
          onError?.(saved.error ?? `Failed to save ${row.label}`)
          return
        }
        refreshRow(row.id, { connected: true, credential_id: saved.credential_id ?? null })
        setDraftSecrets((current) => ({ ...current, [row.id]: '' }))
        setExpandedId(null)
        onStatus?.(`Saved ${row.label} for the workspace.`)
        if (row.category === 'llm') onConnected?.()
        void loadProviders()
        return
      }
      const saved = await workframeAuthApi.saveUserCredential({
        provider: row.id,
        credential_type:
          row.connect_mode === 'bot_token' ? 'bot_token' : row.connect_mode === 'oauth' ? 'api_key' : 'api_key',
        secret,
        env_var: row.env_var,
        label: row.label,
      })
      refreshRow(row.id, { connected: true, credential_id: saved.credential_id })
      for (const extraVar of row.extra_env_vars ?? []) {
        const extraSecret = (draftExtraSecrets[row.id]?.[extraVar] ?? '').trim()
        if (extraSecret) {
          await workframeAuthApi.saveUserCredential({
            provider: row.id,
            credential_type: 'bot_token',
            secret: extraSecret,
            env_var: extraVar,
            label: `${row.label} ${extraVar}`,
          })
        }
      }
      setDraftSecrets((current) => ({ ...current, [row.id]: '' }))
      setDraftExtraSecrets((current) => ({ ...current, [row.id]: {} }))
      setExpandedId(null)
      onStatus?.(`Saved ${row.label} to your Hermes profile.`)
      if (row.category === 'llm') onConnected?.()
      void loadProviders()
    } catch (err) {
      onError?.(err instanceof Error ? err.message : `Failed to save ${row.label}`)
    } finally {
      setBusyId(null)
    }
  }

  const startOAuth = async (row: ProviderConnectRow) => {
    if (isDeviceOAuthProvider(row.id)) {
      onStatusRef.current?.('')
      setDeviceOAuthRow(row)
      return
    }
    setBusyId(row.id)
    onError?.('')
    try {
      const result = await workframeAuthApi.startProviderOAuth(row.id, workspaceId)
      if (result.redirect_url) {
        window.location.assign(result.redirect_url)
        return
      }
      if (result.output) {
        setOauthOutput((current) => ({ ...current, [row.id]: result.output ?? '' }))
      }
      if (result.ok) {
        refreshRow(row.id, { connected: true })
        onStatus?.(`Started ${row.label} OAuth — finish in the opened window or follow the CLI output below.`)
      } else {
        onError?.(result.message || result.output || result.error || `Could not start ${row.label} OAuth`)
      }
      void loadProviders()
    } catch (err) {
      onError?.(err instanceof Error ? err.message : `Failed to start ${row.label} OAuth`)
    } finally {
      setBusyId(null)
    }
  }

  const onDeviceOAuthConnected = useCallback(() => {
    const row = deviceOAuthRowRef.current
    if (!row) return
    refreshRow(row.id, { connected: true })
    onStatusRef.current?.(`Connected ${row.label}.`)
    if (row.category === 'llm') onConnectedRef.current?.()
    void loadProviders()
    setDeviceOAuthRow(null)
  }, [loadProviders])

  const onToggle = async (row: ProviderConnectRow, nextOn: boolean) => {
    if (disabled || busyId) return
    if (!nextOn && credentialScope === 'user' && row.source === 'workspace') {
      onStatus?.('This provider is funded by your Workframe. A Workframe admin manages the shared key.')
      return
    }
    if (nextOn) {
      if (row.connect_mode === 'oauth') {
        if (row.id === 'github' && row.oauth_configured === false) {
          setExpandedId(row.id)
          onStatus?.('Paste a personal access token below, or use OAuth if your admin configured it.')
          return
        }
        if (row.id === 'stripe' && row.oauth_configured === false) {
          onError?.('Ask your Workframe admin to register Stripe Connect under Integrations first.')
          return
        }
        await startOAuth(row)
        return
      }
      setExpandedId(row.id)
      onStatus?.(`Paste your ${row.label} secret, then save.`)
      return
    }
    if (row.connected) {
      await disconnect(row)
    } else {
      setExpandedId(null)
    }
  }

  if (loading && !providers.length) {
    return <PanelStatus>Loading integrations…</PanelStatus>
  }

  if (deviceOAuthRow && deviceOAuthPresentation === 'inline') {
    return (
      <DeviceCodeOAuthFlow
        row={deviceOAuthRow}
        workspaceId={workspaceId}
        active
        presentation="inline"
        reportToParent={false}
        onActiveChange={(next) => {
          if (!next) setDeviceOAuthRow(null)
        }}
        onConnected={onDeviceOAuthConnected}
      />
    )
  }

  const visibleGroups =
    layout === 'tabs' && activeCategory
      ? grouped.filter(([category]) => category === activeCategory)
      : grouped

  return (
    <div className={`wf-provider-connect${layout === 'tabs' ? ' wf-provider-connect--tabs' : ''}`}>
      {hint === 'full' ? (
        <p className="wf-connect-panel__hint wf-connect-panel__hint--security">
          {credentialScope === 'workspace' ? (
            <>Shared workframe credentials — vault-encrypted and synced to the gateway.</>
          ) : (
            <>
              Keys here are <strong>yours</strong> — agents, kanban, and dev actions bill and authenticate as you.
              Workframe bot tokens and OAuth apps are configured under Workframe Settings → Integrations.
            </>
          )}
        </p>
      ) : hint === 'compact' ? (
        <p className="wf-connect-panel__hint wf-connect-panel__hint--inline">
          {credentialScope === 'workspace'
            ? 'Shared workframe keys — vault-encrypted.'
            : 'Your keys — saved to your Hermes profile.'}
        </p>
      ) : null}

      {layout === 'tabs' && grouped.length > 1 ? (
        <div className="wf-provider-connect__tabs" role="tablist" aria-label="Integration categories">
          {grouped.map(([category]) => (
            <button
              key={category}
              type="button"
              role="tab"
              aria-selected={activeCategory === category}
              className={`wf-provider-connect__tab${activeCategory === category ? ' is-active' : ''}`}
              onClick={() => setActiveCategory(category)}
            >
              {PROVIDER_CATEGORY_LABELS[category] ?? category}
            </button>
          ))}
        </div>
      ) : null}

      <div
        className={
          layout === 'tabs' && scrollInner
            ? 'wf-provider-connect__tab-panel wf-scroll wf-scroll--vertical'
            : layout === 'tabs'
              ? 'wf-provider-connect__tab-panel'
              : undefined
        }
      >
      {visibleGroups.map(([category, rows]) => (
        <ProviderList key={category} title={PROVIDER_CATEGORY_LABELS[category] ?? category}>
          {rows.map((row) => (
              <ProviderOptionRow
                key={row.id}
                row={row}
                disabled={disabled}
                isBusy={busyId === row.id}
                isExpanded={expandedId === row.id}
                secretDraft={draftSecrets[row.id] ?? ''}
                draftExtraSecrets={draftExtraSecrets[row.id] ?? {}}
                oauthOutput={oauthOutput[row.id]}
                lockSharedCredential={credentialScope === 'user'}
                onToggle={(nextOn) => void onToggle(row, nextOn)}
                onSecretChange={(value) =>
                  setDraftSecrets((current) => ({ ...current, [row.id]: value }))
                }
                onExtraSecretChange={(envVar, value) =>
                  setDraftExtraSecrets((current) => ({
                    ...current,
                    [row.id]: { ...(current[row.id] ?? {}), [envVar]: value },
                  }))
                }
                onCancel={() => setExpandedId(null)}
                onSave={() => void saveSecret(row)}
                onOAuth={() => void startOAuth(row)}
              />
          ))}
        </ProviderList>
      ))}
      </div>

      <DeviceCodeOAuthFlow
        row={deviceOAuthRow}
        workspaceId={workspaceId}
        active={deviceOAuthRow !== null}
        presentation="dialog"
        onActiveChange={(next) => {
          if (!next) setDeviceOAuthRow(null)
        }}
        onConnected={onDeviceOAuthConnected}
        onError={onError}
      />
    </div>
  )
}
