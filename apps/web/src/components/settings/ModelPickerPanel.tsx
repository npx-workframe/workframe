import { useEffect, useMemo, useState } from 'react'

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

function providerLabel(provider: string): string {
  const key = provider.trim().toLowerCase()
  if (key === 'openrouter') return 'OpenRouter'
  if (key === 'openai') return 'OpenAI'
  if (key === 'anthropic') return 'Anthropic'
  if (key === 'google') return 'Google Gemini'
  if (key === 'deepseek') return 'DeepSeek'
  if (key === 'nous') return 'Nous Portal'
  return provider
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
}: ModelPickerPanelProps) {
  const [data, setData] = useState<HermesModelsResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [customModel, setCustomModel] = useState('')
  const [activeSlot, setActiveSlot] = useState<ModelSlot>('primary')
  const [filterProvider, setFilterProvider] = useState<string | null>(null)
  const [draftFallbacks, setDraftFallbacks] = useState<[FallbackEntry | null, FallbackEntry | null]>([
    null,
    null,
  ])

  useEffect(() => {
    fetchHermesModels(selectionOnly ? undefined : profile, workspaceId)
      .then((res) => {
        if (!res.ok) {
          onError?.('Could not load model surface')
          return
        }
        setData(res)
        if (selectionOnly) {
          const chain = res.fallback_chain ?? []
          setDraftFallbacks([chain[0] ?? null, chain[1] ?? null])
        }
      })
      .catch((err) => onError?.(err instanceof Error ? err.message : 'load failed'))
  }, [onError, profile, selectionOnly, workspaceId])

  const grouped = useMemo(() => {
    const map = new Map<string, HermesModelRow[]>()
    const seenModels = new Set<string>()
    for (const row of data?.suggestions ?? []) {
      if (seenModels.has(row.model)) continue
      seenModels.add(row.model)
      const bucket = map.get(row.provider) ?? []
      bucket.push(row)
      map.set(row.provider, bucket)
    }
    return map
  }, [data?.suggestions])

  const providers = useMemo(() => [...grouped.keys()].sort(), [grouped])

  const filteredGroups = useMemo(() => {
    if (!filterProvider) return [...grouped.entries()]
    const rows = grouped.get(filterProvider)
    return rows ? [[filterProvider, rows] as const] : []
  }, [filterProvider, grouped])

  async function applyFallbackChain(next: FallbackEntry[]) {
    if (!data || selectionOnly) return
    setBusy(true)
    try {
      const res = await setHermesFallbackChain(
        next.map((entry) => ({ provider: entry.provider, model: entry.model })),
        profile ?? data.profile,
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
      const res = await fetchHermesModels(selectionOnly ? undefined : profile, workspaceId)
      if (res.ok) setData(res)
    } catch {
      /* ponytail: best-effort resync after save */
    }
  }

  async function pickModel(model: string) {
    const trimmed = model.trim()
    if (busy || !data || !trimmed) return

    if (selectionOnly) {
      if (activeSlot === 'primary') {
        if (trimmed === value) return
        onChanged?.(trimmed)
        return
      }
      const row = rowForModel(data, trimmed)
      if (!row) {
        onError?.('Pick a model from the list for fallbacks.')
        return
      }
      const entry: FallbackEntry = { provider: row.provider, model: row.model }
      const idx = activeSlot === 'fallback-0' ? 0 : 1
      const next: [FallbackEntry | null, FallbackEntry | null] = [...draftFallbacks]
      next[idx] = entry
      updateDraftFallbacks(next)
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
        const res = await setHermesModel(trimmed, profile ?? data.profile, workspaceId)
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

    const row = rowForModel(data, trimmed)
    if (!row) {
      onError?.('Pick a model from the list for fallbacks.')
      return
    }
    const entry: FallbackEntry = { provider: row.provider, model: row.model }
    const fb = data.fallback_chain ?? []
    const slots: Array<FallbackEntry | null> = [fb[0] ?? null, fb[1] ?? null]
    const idx = activeSlot === 'fallback-0' ? 0 : 1
    slots[idx] = entry
    const next = slots.filter((item): item is FallbackEntry => Boolean(item?.provider && item?.model))
    setPending(trimmed)
    await applyFallbackChain(next)
  }

  if (!data) {
    return <p className="wf-auth__status">Loading models…</p>
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
                  onSelect={() => void pickModel(row.model)}
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
