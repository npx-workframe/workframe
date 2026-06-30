/// <reference types="electron" />

import type { DesktopBridge } from './bridgeTypes'

declare global {
  interface Window {
    workframe?: DesktopBridge
  }
}
