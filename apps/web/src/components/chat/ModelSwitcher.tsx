import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/ui/BrandMark'
import { useCommandDialogs } from '@/contexts/CommandDialogsContext'
import { formatComposerModelLabel } from '@/lib/chatTypes'
import { inferProviderFromModelId, providerIconForId } from '@/lib/workframeAssets'
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
  const label = inactive ? 'Connect provider' : formatComposerModelLabel(providerId, modelId)
  const inferredProvider = inferProviderFromModelId(modelId)
  const iconProviderId = providerIconForId(providerId)
    ? providerId
    : inferredProvider && providerIconForId(inferredProvider)
      ? inferredProvider
      : providerIconForId(modelId.split('/')[0] ?? '')
        ? modelId.split('/')[0]
        : ''

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
          ? 'Connect OpenRouter or another LLM integration'
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
      {!inactive && iconProviderId ? (
        <BrandMark providerId={iconProviderId} className="wf-composer__model-provider" />
      ) : null}
      <span>{label}</span>
    </Button>
  )
}
