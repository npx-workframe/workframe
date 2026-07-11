import { IntegrationsStack } from '@/components/settings/IntegrationsStack'

type WorkframeIntegrationsStepProps = {
  disabled?: boolean
  onBindOAuthSave?: (save: () => Promise<boolean>) => void
  onError?: (message: string) => void
}

/** Onboarding wizard sign-in integrations — delegates to IntegrationsStack. */
export function WorkframeIntegrationsStep({
  disabled,
  onBindOAuthSave,
}: WorkframeIntegrationsStepProps) {
  return <IntegrationsStack variant="onboarding" disabled={disabled} onBindOAuthSave={onBindOAuthSave} />
}
