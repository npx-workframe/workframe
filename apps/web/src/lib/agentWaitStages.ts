/** Cosmetic staged copy while waiting for first stream chunk — not tied to server phases. */
export const AGENT_WAIT_STAGES = [
  'Loading agent profile…',
  'Securing credentials…',
  'Assembling context…',
  'Syncing ledger…',
  'Initializing model…',
  'Opening gateway…',
] as const

export const AGENT_WAIT_STEP_MS = 2800
