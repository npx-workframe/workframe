import { useEffect, useEffectEvent, useMemo, useState } from 'react'

import { ModelListGroup } from '@/components/settings/ModelListGroup'
import { ModelOptionButton } from '@/components/settings/ModelOptionButton'
import { DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { PanelStatus } from '@/components/ui/PanelPrimitives'
import { BrandMark } from '@/components/ui/BrandMark'
import { Input } from '@/components/ui/input'
import {
  fetchHermesModels,
  setHermesFallbackChain,
  setHermesModel,
  type FallbackEntry,
  type HermesModelRow,
  type HermesModelsResponse,
} from '@/lib/hermesCatalogApi'
import { resolveProviderDisplayLabel } from '@/lib/chatTypes'
import { invalidateWorkframeMetaCache } from '@/lib/workframeMetaApi'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { cn } from '@/lib/utils'

type ModelPickerPanelProps = {
  profile?: string
  workspaceId?: string
  compact?: boolean
  /** Embedded in settings shell — taller list fills modal body. */
  embedded?: boolean
  /** List models from user/workspace keys only — do not read or write a Hermes profile. */
  selectionOnly?: boolean
  /** Draft a new agent's model chain without changing user or profile defaults. */
  draftOnly?: boolean
  value?: string
  onChanged?: (model: string) => void
  /** Draft fallback chain while picking models before a profile exists. */
  onFallbacksDraftChange?: (chain: FallbackEntry[]) => void
  onError?: (message: string) => void
  onStatus?: (message: string) => void
  onLoaded?: (data: HermesModelsResponse) => void
}

function pickerErrorMessage(err: unknown, fallback: string): string {
  const text = formatWorkframeErrorMessage(err).trim()
  return text || fallback
}

type ModelSlot = 'primary' | 'fallback-0' | 'fallback-1'

const SLOT_META: Array<{ id: ModelSlot; label: string; hint: string }> = [
  { id: 'primary', label: 'Primary', hint: 'Default model for this agent' },
  { id: 'fallback-0', label: 'Fallback 1', hint: 'Used when primary is unavailable' },
  { id: 'fallback-1', label: 'Fallback 2', hint: 'Second backup in the chain' },
]

function modelLabel(data: HermesModelsResponse | null, modelId: string): string {
  if (!modelId) return '—'
  return data?.suggestions.find((row) => row.model === modelId)?.label?.trim() || modelId
}

function rowForModel(data: HermesModelsResponse, modelId: string): HermesModelRow | null {
  return data.suggestions.find((row) => row.model === modelId) ?? null
}

function billingIdForRow(row: HermesModelRow): string {
  return (row.billing_provider || row.provider || '').trim()
}

function providerLabel(provider: string, modelId = ''): string {
  return resolveProviderDisplayLabel(provider, modelId) || provider
}

function providerBucketKey(provider: string): string {
  const k = provider.trim().toLowerCase().replace(/_/g, '-')
  if (k === 'openai-codex' || k === 'codex' || k === 'openai codex') return 'codex'
  if (k === 'openrouter') return 'openrouter'
  if (k === 'openai') return 'openai'
  if (k === 'anthropic') return 'anthropic'
  if (k === 'google' || k === 'gemini') return 'google'
  if (k === 'deepseek') return 'deepseek'
  if (k === 'nous') return 'nous'
  return k
}

function slotStatusMessage(slot: ModelSlot, modelId: string, data: HermesModelsResponse | null): string {
  const label = SLOT_META.find((entry) => entry.id === slot)?.label ?? 'Model'
  const name = modelLabel(data, modelId)
  return `${label} set to ${name}.`
}

export function ModelPickerPanel({
  profile,
  workspaceId,
  compact,
  embedded = false,
  selectionOnly = false,
  draftOnly = false,
  value,
  onChanged,
  onFallbacksDraftChange,
  onError,
  onStatus,
  onLoaded,
}: ModelPickerPanelProps) {
  const [data, setData] = useState<HermesModelsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [customModel, setCustomModel] = useState('')
  const [activeSlot, setActiveSlot] = useState<ModelSlot>('primary')
  const [filterProvider, setFilterProvider] = useState<string | null>(null)
  const [draftFallbacks, setDraftFallbacks] = useState<[FallbackEntry | null, FallbackEntry | null]>([
    null,
    null,
  ])
  const reportLoadError = useEffectEvent((message: string) => onError?.(message))
  const reportLoaded = useEffectEvent((res: HermesModelsResponse) => {
    onLoaded?.(res)
    if (selectionOnly || draftOnly) {
      const chain = res.fallback_chain ?? []
      setDraftFallbacks([chain[0] ?? null, chain[1] ?? null])
      const seed = (res.primary || res.default_primary || '').trim()
      if (seed) onChanged?.(seed)
    }
  })

  useEffect(() => {
    let cancelled = false
    const catalogOnly = selectionOnly || draftOnly
    fetchHermesModels(catalogOnly ? undefined : profile, workspaceId, { selectionOnly: catalogOnly })
      .then((res) => {
        if (cancelled) return
        if (!res.ok) {
          const message = 'Could not load models'
          setLoadError(message)
          reportLoadError(message)
          return
        }
        setLoadError('')
        setData(res)
        const selectedModel = res.primary || res.default_primary || ''
        const selectedRow = res.suggestions.find((row) => row.model === selectedModel)
        const selectedProvider = selectedRow
          ? providerBucketKey(billingIdForRow(selectedRow))
          : providerBucketKey(res.billing_provider || res.provider || '')
        setFilterProvider(selectedProvider || null)
        reportLoaded(res)
      })
      .catch((err) => {
        if (cancelled) return
        const message = pickerErrorMessage(err, 'Could not load models')
        setLoadError(message)
        reportLoadError(message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [draftOnly, profile, selectionOnly, workspaceId])

  const grouped = useMemo(() => {
    const map = new Map<string, HermesModelRow[]>()
    const seenModels = new Set<string>()
    for (const row of data?.suggestions ?? []) {
      const bucket = providerBucketKey(billingIdForRow(row))
      const key = `${bucket}:${row.model}`
      if (seenModels.has(key)) continue
      seenModels.add(key)
      const list = map.get(bucket) ?? []
      list.push(row)
      map.set(bucket, list)
    }
    return map
  }, [data?.suggestions])

  const providers = useMemo(() => {
    const available = new Set(grouped.keys())
    for (const provider of data?.connected_providers ?? []) {
      available.add(providerBucketKey(provider))
    }
    return [...available].sort((a, b) => providerLabel(a).localeCompare(providerLabel(b)))
  }, [data?.connected_providers, grouped])

  const filteredGroups = useMemo(() => {
    if (!filterProvider) return [...grouped.entries()]
    const rows = grouped.get(filterProvider)
    return rows ? [[filterProvider, rows] as const] : []
  }, [filterProvider, grouped])

  const emptyCatalogMessage = filterProvider
    ? data?.catalog_status?.[filterProvider]?.message ?? 'No live chat models were returned for this provider.'
    : 'No connected provider returned a live chat model. You can retry later or enter a custom model id.'

  async function applyFallbackChain(next: FallbackEntry[]) {
    if (!data) return
    if (selectionOnly) {
      setBusy(true)
      try {
        const res = await setHermesFallbackChain(
          next.map((entry) => ({ provider: entry.provider, model: entry.model })),
          undefined,
          { selectionOnly: true, workspaceId },
        )
        if (!res.ok) {
          onError?.(res.error ?? 'Failed to set fallbacks')
          return
        }
        setData({ ...data, fallback_chain: res.fallback_chain ?? next })
        updateDraftFallbacks([next[0] ?? null, next[1] ?? null])
        await refreshModels()
      } catch (err) {
        onError?.(pickerErrorMessage(err, 'Failed to set fallbacks'))
      } finally {
        setBusy(false)
        setPending(null)
      }
      return
    }
    setBusy(true)
    try {
      const res = await setHermesFallbackChain(
        next.map((entry) => ({ provider: entry.provider, model: entry.model })),
        profile ?? data.profile,
        { selectionOnly, workspaceId },
      )
      if (!res.ok) {
        onError?.(res.error ?? 'Failed to set fallbacks')
        return
      }
      setData({ ...data, fallback_chain: res.fallback_chain ?? next })
      invalidateWorkframeMetaCache()
      await refreshModels()
    } catch (err) {
      onError?.(pickerErrorMessage(err, 'Failed to set fallbacks'))
    } finally {
      setBusy(false)
      setPending(null)
    }
  }

  function updateDraftFallbacks(next: [FallbackEntry | null, FallbackEntry | null]) {
    setDraftFallbacks(next)
    onFallbacksDraftChange?.(next.filter((entry): entry is FallbackEntry => Boolean(entry?.provider && entry?.model)))
  }

  async function refreshModels() {
    try {
      const catalogOnly = selectionOnly || draftOnly
      const res = await fetchHermesModels(catalogOnly ? undefined : profile, workspaceId, { selectionOnly: catalogOnly })
      if (res.ok) setData(res)
    } catch {
      /* ponytail: best-effort resync after save */
    }
  }

  async function pickModel(model: string, billingHint = '') {
    const trimmed = model.trim()
    if (busy || !data || !trimmed) return

    const customEntry = (): FallbackEntry | null => {
      const slash = trimmed.indexOf('/')
      if (slash <= 0) return null
      return { provider: trimmed.slice(0, slash), model: trimmed }
    }

    if (selectionOnly || draftOnly) {
      if (activeSlot === 'primary') {
        if (trimmed === value) return
        if (draftOnly) {
          onChanged?.(trimmed)
          onStatus?.(slotStatusMessage('primary', trimmed, data))
          return
        }
        setBusy(true)
        try {
          const res = await setHermesModel(trimmed, undefined, workspaceId, {
            selectionOnly: true,
            billingProvider: billingHint,
          })
          if (!res.ok) {
            onError?.(res.error ?? 'Failed to set model')
            return
          }
          onChanged?.(res.model ?? trimmed)
          onStatus?.(slotStatusMessage('primary', res.model ?? trimmed, data))
          await refreshModels()
        } catch (err) {
          onError?.(pickerErrorMessage(err, 'Failed to set model'))
        } finally {
          setBusy(false)
        }
        return
      }
      const row = rowForModel(data, trimmed) ?? customEntry()
      if (!row) {
        onError?.('Use provider/model format for custom fallbacks (e.g. openrouter/owl-alpha).')
        return
      }
      const entry: FallbackEntry = {
        provider: billingIdForRow(row as HermesModelRow) || row.provider,
        model: row.model,
      }
      const idx = activeSlot === 'fallback-0' ? 0 : 1
      const next: [FallbackEntry | null, FallbackEntry | null] = [...draftFallbacks]
      next[idx] = entry
      updateDraftFallbacks(next)
      if (draftOnly) {
        onStatus?.(slotStatusMessage(activeSlot, trimmed, data))
        return
      }
      const chain = next.filter((item): item is FallbackEntry => Boolean(item?.provider && item?.model))
      await applyFallbackChain(chain)
      onStatus?.(slotStatusMessage(activeSlot, trimmed, data))
      return
    }

    if (activeSlot === 'primary') {
      if (trimmed === data.primary) {
        onChanged?.(trimmed)
        return
      }
      setBusy(true)
      setPending(trimmed)
      try {
        const catalogRow = rowForModel(data, trimmed)
        const custom = customEntry()
        const billing = catalogRow
          ? billingIdForRow(catalogRow)
          : custom
            ? custom.provider
            : billingHint
        const res = await setHermesModel(trimmed, profile ?? data.profile, workspaceId, {
          billingProvider: billing,
        })
        if (!res.ok) {
          onError?.(res.error ?? 'Failed to set model')
          return
        }
        const saved = res.model ?? trimmed
        setData({ ...data, primary: saved })
        onChanged?.(saved)
        onStatus?.(slotStatusMessage('primary', saved, data))
        invalidateWorkframeMetaCache()
        await refreshModels()
      } catch (err) {
        onError?.(pickerErrorMessage(err, 'Failed to set model'))
      } finally {
        setBusy(false)
        setPending(null)
      }
      return
    }

    const row = rowForModel(data, trimmed) ?? customEntry()
    if (!row) {
      onError?.('Use provider/model format for custom fallbacks (e.g. openrouter/owl-alpha).')
      return
    }
    const entry: FallbackEntry = {
      provider: 'billing_provider' in row ? billingIdForRow(row) : row.provider,
      model: row.model,
    }
    const fb = data.fallback_chain ?? []
    const slots: Array<FallbackEntry | null> = [fb[0] ?? null, fb[1] ?? null]
    const idx = activeSlot === 'fallback-0' ? 0 : 1
    slots[idx] = entry
    const next = slots.filter((item): item is FallbackEntry => Boolean(item?.provider && item?.model))
    setPending(trimmed)
    await applyFallbackChain(next)
    onStatus?.(slotStatusMessage(activeSlot, trimmed, data))
  }

  if (loading) {
    return <PanelStatus>Loading models…</PanelStatus>
  }

  if (loadError) {
    return <p className="text-sm text-muted-foreground">{loadError}</p>
  }

  if (!data) {
    return <p className="text-sm text-muted-foreground">Could not load models.</p>
  }

  const catalogOnly = selectionOnly || draftOnly
  const primaryModel = catalogOnly ? (value ?? '') : (data.primary || '')
  const chain = data.fallback_chain ?? []
  const fallback0 = catalogOnly ? (draftFallbacks[0]?.model ?? '') : (chain[0]?.model ?? '')
  const fallback1 = catalogOnly ? (draftFallbacks[1]?.model ?? '') : (chain[1]?.model ?? '')

  const slotModels: Record<ModelSlot, string> = {
    primary: primaryModel,
    'fallback-0': fallback0,
    'fallback-1': fallback1,
  }
  const slotModel = slotModels[activeSlot]

  if (!data.has_llm_provider) {
    return (
      <p className="text-sm text-muted-foreground">
        Connect an LLM integration first.
      </p>
    )
  }

  return (
    <div className={cn('wf-llm-models', compact && 'wf-llm-models--compact', embedded && 'wf-llm-models--embedded')}>
      <div className="wf-llm-models__slots" role="tablist" aria-label="Model slots">
        {SLOT_META.map((slot) => {
          const modelId = slotModels[slot.id]
          return (
            <button
              key={slot.id}
              type="button"
              role="tab"
              aria-selected={activeSlot === slot.id}
              className={cn(
                'wf-llm-models__slot',
                activeSlot === slot.id && 'is-active',
                modelId && 'is-filled',
              )}
              onClick={() => {
                setActiveSlot(slot.id)
                const selectedRow = rowForModel(data, modelId)
                if (selectedRow) {
                  setFilterProvider(providerBucketKey(billingIdForRow(selectedRow)))
                }
              }}
              disabled={busy}
              title={modelId || slot.hint}
            >
              <span className="wf-llm-models__slot-label">{slot.label}</span>
              <span className="wf-llm-models__slot-value">{modelLabel(data, modelId)}</span>
            </button>
          )
        })}
      </div>

      <div className="wf-llm-models__body">
        {providers.length > 1 ? (
          <div className="wf-llm-models__providers" role="tablist" aria-label="Filter by integration">
            <button
              type="button"
              role="tab"
              aria-selected={filterProvider === null}
              className={cn('wf-llm-models__provider', filterProvider === null && 'is-active')}
              onClick={() => setFilterProvider(null)}
            >
              All
            </button>
            {providers.map((provider) => {
              return (
                <button
                  key={provider}
                  type="button"
                  role="tab"
                  aria-selected={filterProvider === provider}
                  className={cn('wf-llm-models__provider', filterProvider === provider && 'is-active')}
                  onClick={() => setFilterProvider(provider)}
                >
                  <BrandMark providerId={provider} className="wf-llm-models__provider-icon" />
                  {providerLabel(provider)}
                </button>
              )
            })}
          </div>
        ) : null}

        <div
          className={cn(
            'wf-llm-models__list',
            embedded ? 'wf-llm-models__list--embedded' : compact ? 'wf-llm-models__list--compact' : '',
          )}
        >
          {filteredGroups.length ? (
            filteredGroups.map(([provider, rows]) => (
              <ModelListGroup key={provider} provider={providerLabel(provider)}>
                {rows.map((row) => (
                  <ModelOptionButton
                    key={`${billingIdForRow(row)}:${row.model}`}
                    label={row.label}
                    model={row.model}
                    provider={row.provider}
                    isCurrent={row.model === slotModel}
                    isPending={!catalogOnly && pending === row.model}
                    disabled={busy}
                    singleLine
                    onSelect={() => void pickModel(row.model, billingIdForRow(row))}
                  />
                ))}
              </ModelListGroup>
            ))
          ) : (
            <PanelStatus>{emptyCatalogMessage}</PanelStatus>
          )}
        </div>

        {!compact ? (
          <div className="wf-llm-models__custom">
            <label className="wf-dialog-field__label" htmlFor="wf-model-custom-panel">
              Other model ID
            </label>
            <div className="wf-dialog__custom-model-row">
              <Input
                id="wf-model-custom-panel"
                className="wf-dialog-input"
                value={customModel}
                onChange={(event) => setCustomModel(event.target.value)}
                placeholder={filterProvider === 'openrouter' ? 'vendor/model-id' : 'model-id'}
                disabled={busy}
              />
              <DialogConfirmButton
                onClick={() => void pickModel(customModel, filterProvider ?? '')}
                disabled={busy || !customModel.trim()}
              >
                Set
              </DialogConfirmButton>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
