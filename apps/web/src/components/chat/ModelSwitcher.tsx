import { Button } from '@/components/ui/button'
import { useCommandDialogs } from '@/contexts/CommandDialogsContext'
import { modelLabelFromId } from '@/lib/chatTypes'
import { inferProviderFromModelId, providerIconForId } from '@/lib/workframeAssets'
import { cn } from '@/lib/utils'

type ModelSwitcherProps = {
  modelId: string
  hasProvider?: boolean
  onConnectProvider?: () => void
}

/** Model badge — opens picker when configured, otherwise routes to provider setup. */
export function ModelSwitcher({ modelId, hasProvider = true, onConnectProvider }: ModelSwitcherProps) {
  const { openModelPicker } = useCommandDialogs()
  const inactive = !hasProvider
  const label = inactive ? 'Connect provider' : modelLabelFromId(modelId)
  const provider =
    providerIconForId(inferProviderFromModelId(modelId)) ??
    providerIconForId(modelId.split('/')[0] ?? '')

  return (
    <Button
      type="button"
      variant="toolbar"
      size="toolbarText"
      className={cn('wf-composer__model-trigger', inactive && 'wf-composer__model-trigger--inactive')}
      aria-label={inactive ? 'Connect a model provider' : `Active model: ${label}. Click to change.`}
      title={inactive ? 'Connect OpenRouter or another LLM provider' : modelId || 'Model from Hermes profile'}
      onClick={() => {
        if (inactive) {
          onConnectProvider?.()
          return
        }
        openModelPicker()
      }}
    >
      {!inactive && provider ? (
        <img
          src={provider}
          alt=""
          aria-hidden="true"
          className="wf-composer__model-provider"
        />
      ) : null}
      <span>{label}</span>
    </Button>
  )
}
