import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import { normalizePublicUrl } from '@/components/onboarding/conciergeFlowUtils'
import { formatWorkframeError, type WorkframeNoticeInfo } from '@/lib/workframeErrors'

export type ConciergePublishContinueDeps = {
  publicUrl: string
  setPublicUrl: (url: string) => void
  patchInstallStackWhenAllowed: (data: Record<string, unknown>) => Promise<boolean>
  setStep: (step: ConciergeStep) => void
  setBusy: (busy: boolean) => void
  setError: (error: WorkframeNoticeInfo | null) => void
}

export async function continueFromPublishStep(deps: ConciergePublishContinueDeps) {
  deps.setBusy(true)
  try {
    const url = normalizePublicUrl(deps.publicUrl)
    deps.setPublicUrl(url)
    const patched = await deps.patchInstallStackWhenAllowed({ app_base_url: url })
    if (!patched) return
    deps.setStep('smtp')
  } catch (err) {
    deps.setError(formatWorkframeError(err, 'Save public URL'))
  } finally {
    deps.setBusy(false)
  }
}
