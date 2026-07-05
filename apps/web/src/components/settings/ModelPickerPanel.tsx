import { useEffect, useMemo, useRef, useState } from 'react'

import { ModelListGroup } from '@/components/settings/ModelListGroup'
import { ModelOptionButton } from '@/components/settings/ModelOptionButton'
import { DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { Input } from '@/components/ui/input'
import {
  fetchHermesModels,
  setHermesFallbackChain,
  setHermesModel,
  type FallbackEntry,
  type HermesModelRow,
  type HermesModelsResponse,
} from '@/lib/hermesCatalogApi'
import { providerIconForId } from '@/lib/workframeAssets'
import { billingProviderDisplayLabel } from '@/lib/brandAssets'
import { invalidateWorkframeMetaCache } from '@/lib/workframeMetaApi'
import { cn } from '@/lib/utils'

type ModelPickerPanelProps = {
  profile?: string
  workspaceId?: string
  compact?: boolean
  /** Embedded in settings shell — taller list fills modal body. */
  embedded?: boolean
  /** List models from user/workspace keys only — do not read or write a Hermes profile. */
  selectionOnly?: boolean
  value?: string
  onChanged?: (model: string) => void
  /** Draft fallback chain while picking models before a profile exists. */
  onFallbacksDraftChange?: (chain: FallbackEntry[]) => void
  onError?: (message: string) => void
  onLoaded?: (data: HermesModelsResponse) => void
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

function providerLabel(provider: string): string {
  return billingProviderDisplayLabel(provider) || provider
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

export function ModelPickerPanel({
  profile,
  workspaceId,
  compact,
  embedded = false,
  selectionOnly = false,
  value,
  onChanged,
  onFallbacksDraftChange,
  onError,
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
  const onErrorRef = useRef(onError)
  const onLoadedRef = useRef(onLoaded)
  onErrorRef.current = onError
  onLoadedRef.current = onLoaded

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')
    setData(null)
    fetchHermesModels(selectionOnly ? undefined : profile, workspaceId, { selectionOnly })
      .then((res) => {
        if (cancelled) return
        if (!res.ok) {
          const message = 'Could not load models'
          setLoadError(message)
          onErrorRef.current?.(message)
          return
        }
        setData(res)
        onLoadedRef.current?.(res)
        if (selectionOnly) {
          const chain = res.fallback_chain ?? []
          setDraftFallbacks([chain[0] ?? null, chain[1] ?? null])
        }
      })
      .catch((err) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'load failed'
        setLoadError(message)
        onErrorRef.current?.(message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [profile, selectionOnly, workspaceId])

  const grouped = useMemo(() => {
    const map = new Map<string, HermesModelRow[]>()
    const seenModels = new Set<string>()
    for (const row of data?.suggestions ?? []) {
      if (seenModels.has(row.model)) continue
      seenModels.add(row.model)
      const bucket = providerBucketKey(billingIdForRow(row))
      const list = map.get(bucket) ?? []
      list.push(row)
      map.set(bucket, list)
    }
    return map
  }, [data?.suggestions])

  const providers = useMemo(
    () => [...grouped.keys()].sort((a, b) => providerLabel(a).localeCompare(providerLabel(b))),
    [grouped],
  )

  const filteredGroups = useMemo(() => {
    if (!filterProvider) return [...grouped.entries()]
    const rows = grouped.get(filterProvider)
    return rows ? [[filterProvider, rows] as const] : []
  }, [filterProvider, grouped])

  async function applyFallbackChain(next: FallbackEntry[]) {
    if (!data) return
    if (selectionOnly) {
      setBusy(true)
      try {
        const res = await setHermesFallbackChain(
          next.map((entry) => ({ provider: entry.provider, model: entry.model })),
          undefined,
          { selectionOnly: true },
        )
        if (!res.ok) {
          onError?.(res.error ?? 'Failed to set fallbacks')
          return
        }
        setData({ ...data, fallback_chain: res.fallback_chain ?? next })
        updateDraftFallbacks([next[0] ?? null, next[1] ?? null])
        await refreshModels()
      } catch (err) {
        onError?.(err instanceof Error ? err.message : 'set failed')
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
        { selectionOnly },
      )
      if (!res.ok) {
        onError?.(res.error ?? 'Failed to set fallbacks')
        return
      }
      setData({ ...data, fallback_chain: res.fallback_chain ?? next })
      invalidateWorkframeMetaCache()
      await refreshModels()
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'set failed')
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
      const res = await fetchHermesModels(selectionOnly ? undefined : profile, workspaceId, { selectionOnly })
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

    if (selectionOnly) {
      if (activeSlot === 'primary') {
        if (trimmed === value) return
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
          await refreshModels()
        } catch (err) {
          onError?.(err instanceof Error ? err.message : 'set failed')
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
      const chain = next.filter((item): item is FallbackEntry => Boolean(item?.provider && item?.model))
      await applyFallbackChain(chain)
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
        invalidateWorkframeMetaCache()
        await refreshModels()
      } catch (err) {
        onError?.(err instanceof Error ? err.message : 'set failed')
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
  }

  if (loading) {
    return <p className="wf-auth__status">Loading models…</p>
  }

  if (loadError) {
    return <p className="text-sm text-muted-foreground">{loadError}</p>
  }

  if (!data) {
    return <p className="text-sm text-muted-foreground">Could not load models.</p>
  }

  const primaryModel = selectionOnly ? (value ?? '') : (data.primary || '')
  const chain = data.fallback_chain ?? []
  const fallback0 = selectionOnly ? (draftFallbacks[0]?.model ?? '') : (chain[0]?.model ?? '')
  const fallback1 = selectionOnly ? (draftFallbacks[1]?.model ?? '') : (chain[1]?.model ?? '')

  const slotModels: Record<ModelSlot, string> = {
    primary: primaryModel,
    'fallback-0': fallback0,
    'fallback-1': fallback1,
  }
  const slotModel = slotModels[activeSlot]

  if (!data.has_llm_provider) {
    return (
      <p className="text-sm text-muted-foreground">
        Connect an LLM provider first.
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
              onClick={() => setActiveSlot(slot.id)}
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
          <div className="wf-llm-models__providers" role="tablist" aria-label="Filter by provider">
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
              const icon = providerIconForId(provider)
              return (
                <button
                  key={provider}
                  type="button"
                  role="tab"
                  aria-selected={filterProvider === provider}
                  className={cn('wf-llm-models__provider', filterProvider === provider && 'is-active')}
                  onClick={() => setFilterProvider(provider)}
                >
                  {icon ? (
                    <img src={icon} alt="" className="wf-llm-models__provider-icon" aria-hidden="true" />
                  ) : null}
                  {providerLabel(provider)}
                </button>
              )
            })}
          </div>
        ) : null}

        <div
          className={cn(
            'wf-llm-models__list wf-scroll wf-scroll--vertical',
            embedded ? 'wf-llm-models__list--embedded' : compact ? 'wf-llm-models__list--compact' : '',
          )}
        >
          {filteredGroups.map(([provider, rows]) => (
            <ModelListGroup key={provider} provider={providerLabel(provider)}>
              {rows.map((row) => (
                <ModelOptionButton
                  key={row.model}
                  label={row.label}
                  model={row.model}
                  provider={row.provider}
                  isCurrent={row.model === slotModel}
                  isPending={!selectionOnly && pending === row.model}
                  disabled={busy}
                  singleLine
                  onSelect={() => void pickModel(row.model, billingIdForRow(row))}
                />
              ))}
            </ModelListGroup>
          ))}
        </div>

        {!compact ? (
          <div className="wf-llm-models__custom">
            <label className="wf-dialog-field__label" htmlFor="wf-model-custom-panel">
              Custom model id
            </label>
            <div className="wf-dialog__custom-model-row">
              <Input
                id="wf-model-custom-panel"
                className="wf-dialog-input"
                value={customModel}
                onChange={(event) => setCustomModel(event.target.value)}
                placeholder="openrouter/owl-alpha"
                disabled={busy}
              />
              <DialogConfirmButton
                onClick={() => void pickModel(customModel)}
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
