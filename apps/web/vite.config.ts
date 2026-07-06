import { defineConfig, loadEnv } from 'vite'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const authPort = env.VITE_WORKFRAME_UI_PORT || env.VITE_WORKFRAME_API_PORT || '18644'
  const dashPort = env.VITE_WORKFRAME_DASHBOARD_PORT || '19119'
  const uiPort = env.VITE_WORKFRAME_DEV_PORT || '5173'

  return {
    plugins: [react(), tailwindcss()],
    // ponytail: '/' for nginx/docker SPA (nested paths like /dev/buttons); dev server tolerates either
    base: mode === 'workframe' ? '/' : './',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: Number(uiPort),
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/hermes-dashboard': {
          target: `http://127.0.0.1:${dashPort}`,
          changeOrigin: true,
          ws: true,
          rewrite: (p) => p.replace(/^\/hermes-dashboard/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              proxyReq.setHeader('X-Forwarded-Prefix', '/hermes-dashboard')
              proxyReq.setHeader('X-Forwarded-Proto', 'http')
              proxyReq.setHeader('X-Forwarded-Host', `127.0.0.1:${uiPort}`)
            })
          },
        },
      },
    },
  }
})
