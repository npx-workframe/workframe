import { fetchHermesBootstrap } from '@/lib/hermesDashboardApi'
import { buildWsUrl, dashboardPublicBase } from '@/lib/workframeProfile'

const PTY_CHANNEL = 'workframe-ui'

/** One-shot PTY send — used for session bootstrap (`/new`) when the terminal UI is hidden. */
export async function sendHermesPtyText(text: string): Promise<void> {
  const boot = await fetchHermesBootstrap()
  const dashboardBase = dashboardPublicBase(boot.dashboardUrl)
  const ws = new WebSocket(
    buildWsUrl(dashboardBase, 'api/pty', { token: boot.token, channel: PTY_CHANNEL }),
  )
  ws.binaryType = 'arraybuffer'

  await new Promise<void>((resolve, reject) => {
    ws.onopen = () => resolve()
    ws.onerror = () => reject(new Error('PTY connection failed'))
  })

  ws.send(text)
  ws.close()
}
