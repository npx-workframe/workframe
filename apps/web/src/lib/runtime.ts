export function isElectronRuntime() {
  return typeof window !== 'undefined' && Boolean((window as Window & { workframe?: unknown }).workframe)
}
