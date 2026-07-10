import { useCallback, useEffect, useRef, useState } from 'react'

import { workframeAuthApi } from '@/lib/workframeAuthApi'

export type DeviceCodeOAuthStatus = 'idle' | 'starting' | 'pending' | 'connected' | 'error'

export type UseDeviceCodeOAuthArgs = {
  providerId: string
  providerLabel: string
  workspaceId?: string
  active: boolean
  onConnected?: () => void
  onError?: (message: string) => void
}

function setIfChanged<T>(next: T, apply: (value: T) => void, prev: { current: T }) {
  if (Object.is(prev.current, next)) return
  prev.current = next
  apply(next)
}

function oauthErrorMessage(
  result: { message?: string | null; output?: string | null; error?: string | null },
  fallback: string,
) {
  return (result.message || result.output || result.error || fallback).trim()
}

export function useDeviceCodeOAuth({
  providerId,
  providerLabel,
  workspaceId,
  active,
  onConnected,
  onError,
}: UseDeviceCodeOAuthArgs) {
  const [verificationUri, setVerificationUri] = useState<string | null>(null)
  const [userCode, setUserCode] = useState<string | null>(null)
  const [status, setStatus] = useState<DeviceCodeOAuthStatus>('idle')
  const [message, setMessage] = useState('')
  const [copied, setCopied] = useState(false)
  const pollRef = useRef<number | null>(null)
  const onConnectedRef = useRef(onConnected)
  const onErrorRef = useRef(onError)
  const verificationUriRef = useRef<string | null>(null)
  const userCodeRef = useRef<string | null>(null)
  const startedKeyRef = useRef<string | null>(null)

  onConnectedRef.current = onConnected
  onErrorRef.current = onError

  const clearPoll = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const fail = useCallback(
    (err: string) => {
      clearPoll()
      startedKeyRef.current = null
      setStatus('error')
      setMessage(err)
      onErrorRef.current?.(err)
    },
    [clearPoll],
  )

  const reset = useCallback(() => {
    clearPoll()
    startedKeyRef.current = null
    verificationUriRef.current = null
    userCodeRef.current = null
    setVerificationUri(null)
    setUserCode(null)
    setStatus('idle')
    setMessage('')
    setCopied(false)
  }, [clearPoll])

  useEffect(() => {
    if (!active) {
      reset()
      return
    }
    if (!providerId) return

    const startKey = `${providerId}:${workspaceId ?? ''}`
    if (startedKeyRef.current === startKey) return

    let cancelled = false
    startedKeyRef.current = startKey
    setStatus('starting')
    setMessage('')

    void (async () => {
      try {
        const result = await workframeAuthApi.startProviderOAuth(providerId, workspaceId)
        if (cancelled) return
        if (result.redirect_url) {
          window.location.assign(result.redirect_url)
          return
        }
        if (!result.ok || !result.session_id) {
          fail(oauthErrorMessage(result, `Could not start ${providerLabel} OAuth`))
          return
        }
        setIfChanged(result.verification_uri ?? null, setVerificationUri, verificationUriRef)
        setIfChanged(result.user_code ?? null, setUserCode, userCodeRef)
        if (result.status === 'connected') {
          setStatus('connected')
          setMessage(`${providerLabel} is connected.`)
          onConnectedRef.current?.()
          return
        }
        if (result.status === 'error') {
          fail(oauthErrorMessage(result, `${providerLabel} OAuth failed`))
          return
        }
        setStatus('pending')
        const sessionId = result.session_id
        pollRef.current = window.setInterval(() => {
          void workframeAuthApi
            .providerOAuthStatus(providerId, sessionId)
            .then((poll) => {
              if (cancelled) return
              setIfChanged(poll.verification_uri ?? null, setVerificationUri, verificationUriRef)
              setIfChanged(poll.user_code ?? null, setUserCode, userCodeRef)
              if (poll.status === 'connected' && poll.ok) {
                clearPoll()
                setStatus('connected')
                setMessage(`${providerLabel} is connected.`)
                onConnectedRef.current?.()
                return
              }
              if (poll.status === 'error' || poll.ok === false) {
                fail(oauthErrorMessage(poll, `${providerLabel} OAuth failed`))
              }
            })
            .catch((err: unknown) => {
              if (cancelled) return
              const errMsg = err instanceof Error ? err.message : `${providerLabel} OAuth failed`
              fail(errMsg)
            })
        }, 3000)
      } catch (err) {
        if (cancelled) return
        const errMsg = err instanceof Error ? err.message : `Failed to start ${providerLabel} OAuth`
        fail(errMsg)
      }
    })()

    return () => {
      cancelled = true
      clearPoll()
    }
  }, [active, clearPoll, fail, providerId, providerLabel, reset, workspaceId])

  const copyCode = useCallback(async () => {
    if (!userCode) return
    try {
      await navigator.clipboard.writeText(userCode)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      onErrorRef.current?.('Could not copy code to clipboard')
    }
  }, [userCode])

  return {
    verificationUri,
    userCode,
    status,
    message,
    copied,
    copyCode,
  }
}
