import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchHermesBootstrap } from '@/lib/hermesDashboardApi'
import { buildWsUrl, dashboardPublicBase, normalizePtyChunk } from '@/lib/workframeProfile'

const PTY_CHANNEL = 'workframe-ui'
const DEFAULT_MAX_LINES = 16

function decodePtyPayload(data: string | ArrayBuffer | Blob): string {
  if (typeof data === 'string') return data
  if (data instanceof ArrayBuffer) return new TextDecoder().decode(data)
  return ''
}

export function useHermesPty(maxLines = DEFAULT_MAX_LINES) {
  const wsRef = useRef<WebSocket | null>(null)
  const connectPromiseRef = useRef<Promise<WebSocket> | null>(null)
  const [lines, setLines] = useState<string[]>([])
  const [connected, setConnected] = useState(false)

  const appendLine = useCallback(
    (line: string) => {
      const trimmed = line.trimEnd()
      if (!trimmed) return
      setLines((prev) => [...prev, trimmed].slice(-maxLines))
    },
    [maxLines],
  )

  const appendChunk = useCallback(
    (chunk: string) => {
      const normalized = normalizePtyChunk(chunk)
      if (!normalized) return

      setLines((prev) => {
        const next = [...prev]
        for (const line of normalized.split('\n')) {
          const trimmed = line.trimEnd()
          if (!trimmed) continue
          next.push(trimmed)
        }
        return next.slice(-maxLines)
      })
    },
    [maxLines],
  )

  const connect = useCallback(async (): Promise<WebSocket> => {
    const existing = wsRef.current
    if (existing && existing.readyState === WebSocket.OPEN) return existing

    if (connectPromiseRef.current) return connectPromiseRef.current

    connectPromiseRef.current = (async () => {
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

      ws.onmessage = (event) => {
        appendChunk(decodePtyPayload(event.data as string | ArrayBuffer))
      }
      ws.onclose = () => {
        wsRef.current = null
        connectPromiseRef.current = null
        setConnected(false)
      }

      wsRef.current = ws
      setConnected(true)
      return ws
    })()

    try {
      return await connectPromiseRef.current
    } catch (err) {
      connectPromiseRef.current = null
      throw err
    }
  }, [appendChunk])

  const send = useCallback(
    async (text: string) => {
      const ws = await connect()
      ws.send(text)
    },
    [connect],
  )

  useEffect(() => {
    void connect().catch(() => {
      // Connection errors surface on explicit send attempts.
    })

    return () => {
      wsRef.current?.close()
      wsRef.current = null
      connectPromiseRef.current = null
    }
  }, [connect])

  return { lines, connected, connect, send, appendLine }
}
