/** Providers that use OAuth device-code flow (Hermes CLI) instead of redirect. */
export const DEVICE_OAUTH_PROVIDER_IDS = new Set(['codex', 'nous'])

/** Known device-flow URLs when Hermes has not printed one yet. */
export const DEVICE_OAUTH_VERIFICATION_URIS: Record<string, string> = {
  codex: 'https://auth.openai.com/codex/device',
}

export function isDeviceOAuthProvider(providerId: string): boolean {
  return DEVICE_OAUTH_PROVIDER_IDS.has(providerId)
}

export function deviceOAuthVerificationUri(providerId: string): string | null {
  return DEVICE_OAUTH_VERIFICATION_URIS[providerId] ?? null
}
