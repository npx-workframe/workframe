import { useEffect, useState } from 'react'

import { AGENT_WAIT_STAGES, AGENT_WAIT_STEP_MS } from '@/lib/agentWaitStages'

/** Cycles staged copy while mounted. Parent unmounts when stream content arrives. */
export function WaitHint() {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (AGENT_WAIT_STAGES.length <= 1) return
    const timer = window.setInterval(() => {
      setIndex((prev) => (prev + 1) % AGENT_WAIT_STAGES.length)
    }, AGENT_WAIT_STEP_MS)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <p className="wf-message__live-hint" role="status" aria-live="polite">
      {AGENT_WAIT_STAGES[index]}
    </p>
  )
}
