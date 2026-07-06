import { useEffect, useState } from 'react'

import { OperationProgress, type OperationStep } from '@/components/ui/OperationProgress'

const TAGLINES = [
  'Connecting your agent to Hermes…',
  'Teaching your native agent your mission…',
  'Opening your first chat room…',
  'Almost ready — finishing setup…',
]

type OnboardingLaunchScreenProps = {
  projectName: string
  steps: OperationStep[]
  title?: string
  error?: string | null
}

export function OnboardingLaunchScreen({
  projectName,
  steps,
  title = `Launching ${projectName}`,
  error = null,
}: OnboardingLaunchScreenProps) {
  const [tagline, setTagline] = useState(TAGLINES[0])

  useEffect(() => {
    let index = 0
    const timer = window.setInterval(() => {
      index = (index + 1) % TAGLINES.length
      setTagline(TAGLINES[index]!)
    }, 2800)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="wf-onboarding-launch" role="status" aria-live="polite" aria-busy={!error}>
      <div className="wf-onboarding-launch__card">
        <p className="wf-onboarding-launch__eyebrow">Workframe</p>
        <h1 className="wf-onboarding-launch__title">{title}</h1>
        <p className="wf-onboarding-launch__tagline">{error || tagline}</p>
        <OperationProgress steps={steps} />
      </div>
    </div>
  )
}

export const FINISH_INSTALL_STEP_LABELS = [
  { id: 'runtime_profile', label: 'Create your personal agent runtime' },
  { id: 'bootstrap_providers', label: 'Apply model and provider settings' },
  { id: 'start_gateway', label: 'Start Hermes gateway' },
  { id: 'dm_room', label: 'Open agent chat room' },
  { id: 'room_chat_bind', label: 'Connect chat session' },
  { id: 'finalize', label: 'Load Workframe' },
] as const

export const AGENT_SAVE_STEP_LABELS = [
  { id: 'save_agent', label: 'Save agent identity' },
] as const
