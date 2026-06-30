/** Mask shown in password fields when a secret is already stored server-side. */
export const SAVED_SECRET_MASK = '••••••••'

export function savedSecretPlaceholder(saved: boolean, emptyLabel = 'Paste secret') {
  return saved ? SAVED_SECRET_MASK : emptyLabel
}
