export interface DesktopBridge {
  getConfig: () => Promise<{ lastUrl: string; isFirstRun: boolean }>
  setLastUrl: (url: string) => Promise<void>
  clearLastUrl: () => Promise<void>
  getInviteParams: () => Promise<{ inviteToken: string; email: string }>
  onConnectionChange: (callback: (state: 'connecting' | 'connected' | 'error') => void) => () => void
  getPlatform: () => NodeJS.Platform
  getAppVersion: () => Promise<string>
  minimizeWindow: () => Promise<void>
  toggleMaximizeWindow: () => Promise<{ maximized: boolean }>
  closeWindow: () => Promise<void>
  setBrowserViewBounds: (bounds: { x: number; y: number; width: number; height: number }) => Promise<void>
  setBrowserViewUrl: (url: string) => Promise<void>
  clearBrowserView: () => Promise<void>
}
