/// <reference types="vite/client" />

import type { HTMLAttributes } from 'react'

interface ImportMetaEnv {
  readonly VITE_WORKFRAME_PROJECT?: string
  readonly VITE_WORKFRAME_DASHBOARD_URL?: string
  readonly VITE_WORKFRAME_DASHBOARD_PORT?: string
  readonly VITE_WORKFRAME_API_URL?: string
  readonly VITE_WORKFRAME_API_PORT?: string
  readonly VITE_WORKFRAME_SETUP_URL?: string
  readonly VITE_WORKFRAME_SETUP_PORT?: string
  readonly VITE_WORKFRAME_UI_URL?: string
  readonly VITE_WORKFRAME_UI_PORT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare global {
  namespace JSX {
    interface IntrinsicElements {
      webview: HTMLAttributes<HTMLElement> & {
        src?: string
        allowpopups?: boolean
        partition?: string
        preload?: string
        webpreferences?: string
      }
    }
  }
}
