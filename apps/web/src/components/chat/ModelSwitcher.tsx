import { Button } from '@/components/ui/button'
import { useCommandDialogs } from '@/contexts/CommandDialogsContext'
import { modelLabelFromId } from '@/lib/chatTypes'
import { billingProviderDisplayLabel, inferProviderFromModelId, providerIconForId } from '@/lib/workframeAssets'
import { cn } from '@/lib/utils'

type ModelSwitcherProps = {
  modelId: string
  providerId?: string
  hasProvider?: boolean
  onConnectProvider?: () => void
  /** Read-only agent model badge — opens agent settings instead of picker. */
  readOnly?: boolean
  onOpenAgentModels?: () => void
}

/** Model badge — opens picker when configured, otherwise routes to provider setup. */
export function ModelSwitcher({
  modelId,
  providerId = '',
  hasProvider = true,
  onConnectProvider,
  readOnly = false,
  onOpenAgentModels,
}: ModelSwitcherProps) {
  const { openModelPicker } = useCommandDialogs()
  const inactive = !hasProvider
  const billingProvider =
    billingProviderDisplayLabel(providerId) ||
    billingProviderDisplayLabel(inferProviderFromModelId(modelId)) ||
    ''
  const modelLabel = modelLabelFromId(modelId)
  const label = inactive
    ? 'Connect provider'
    : billingProvider
      ? `${billingProvider} · ${modelLabel}`
      : modelLabel
  const iconProvider =
    providerIconForId(providerId || inferProviderFromModelId(modelId)) ??
    providerIconForId(modelId.split('/')[0] ?? '')

  return (
    <Button
      type="button"
      variant="toolbar"
      size="toolbarText"
      className={cn('wf-composer__model-trigger', inactive && 'wf-composer__model-trigger--inactive')}
      aria-label={
        inactive
          ? 'Connect a model provider'
          : readOnly
            ? `Agent model: ${label}. Open agent settings to change.`
            : `Active model: ${label}. Click to change.`
      }
      title={
        inactive
          ? 'Connect OpenRouter or another LLM provider'
          : readOnly
            ? 'Change model in Agent Settings → LLM Models'
            : modelId || 'Model from Hermes profile'
      }
      onClick={() => {
        if (inactive) {
          onConnectProvider?.()
          return
        }
        if (readOnly) {
          onOpenAgentModels?.()
          return
        }
        openModelPicker()
      }}
    >
      {!inactive && iconProvider ? (
        <img
          src={iconProvider}
          alt=""
          aria-hidden="true"
          className="wf-composer__model-provider"
        />
      ) : null}
      <span>{label}</span>
    </Button>
  )
}
