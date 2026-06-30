/** Native Hermes profile slug for this Workframe install (e.g. workframe-agent). */
export function nativeProfileSlug(): string {
  const explicit = import.meta.env.VITE_WORKFRAME_NATIVE_PROFILE?.trim()
  if (explicit) return explicit
  const project = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  return `${project.toLowerCase().replace(/\s+/g, '')}-agent`
}

export type WorkframeRuntimeConfig = {
  projectName: string
  nativeProfile: string
}

let runtimeConfigPromise: Promise<WorkframeRuntimeConfig> | null = null

/** Load project/profile from baked env or generated workframe-config.json. */
export async function loadWorkframeRuntimeConfig(): Promise<WorkframeRuntimeConfig> {
  if (!runtimeConfigPromise) {
    runtimeConfigPromise = (async () => {
      const envProject = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || ''
      const envProfile = import.meta.env.VITE_WORKFRAME_NATIVE_PROFILE?.trim() || ''

      try {
        const res = await fetch('./workframe-config.json')
        if (res.ok) {
          const data = (await res.json()) as {
            project_name?: string
            native_profile?: string
          }
          const projectName = data.project_name?.trim() || envProject || 'Workframe'
          const nativeProfile =
            data.native_profile?.trim() || envProfile || nativeProfileSlug()
          return { projectName, nativeProfile }
        }
      } catch {
        // generated config is optional in meta dev
      }

      return {
        projectName: envProject || 'Workframe',
        nativeProfile: envProfile || nativeProfileSlug(),
      }
    })()
  }
  return runtimeConfigPromise
}

/** Strip ANSI escape sequences from Hermes PTY / TUI output. */
export function stripAnsi(text: string): string {
  return text
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b[@-_]/g, '')
}

/** Collapse noisy PTY control chars while keeping newlines. */
export function normalizePtyChunk(text: string): string {
  return stripAnsi(text)
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '')
}

/** Same-origin Hermes dashboard base for PTY/events (works in Docker + Vite dev). */
export function dashboardPublicBase(fallbackUrl: string): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return `${window.location.origin}/hermes-dashboard`
  }
  return fallbackUrl.replace(/\/$/, '')
}

/** Build a WebSocket URL under the Hermes dashboard proxy path. */
export function buildWsUrl(
  dashboardBase: string,
  path: string,
  params: Record<string, string>,
): string {
  const rel = path.startsWith('/') ? path.slice(1) : path
  const url = new URL(rel, dashboardBase.endsWith('/') ? dashboardBase : `${dashboardBase}/`)
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value)
  }
  const proto = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${url.host}${url.pathname}${url.search}`
}
