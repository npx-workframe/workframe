import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { ProviderConnectRow } from '@/lib/workframeAuthApi'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type DeviceCodeOAuthDialogProps = {
  row: ProviderConnectRow | null
  workspaceId?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onConnected?: () => void
  onError?: (message: string) => void
}

export function DeviceCodeOAuthDialog({
  row,
  workspaceId,
  open,
  onOpenChange,
  onConnected,
  onError,
}: DeviceCodeOAuthDialogProps) {
  const [verificationUri, setVerificationUri] = useState<string | null>(null)
  const [userCode, setUserCode] = useState<string | null>(null)
  const [status, setStatus] = useState<'starting' | 'pending' | 'connected' | 'error'>('starting')
  const [message, setMessage] = useState('')
  const [copied, setCopied] = useState(false)
  const pollRef = useRef<number | null>(null)

  const clearPoll = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const reset = useCallback(() => {
    clearPoll()
    setVerificationUri(null)
    setUserCode(null)
    setStatus('starting')
    setMessage('')
    setCopied(false)
  }, [clearPoll])

  useEffect(() => {
    if (!open) {
      reset()
      return
    }
    if (!row) return

    let cancelled = false
    reset()
    setStatus('starting')

    void (async () => {
      try {
        const result = await workframeAuthApi.startProviderOAuth(row.id, workspaceId)
        if (cancelled) return
        if (result.redirect_url) {
          window.location.assign(result.redirect_url)
          return
        }
        if (!result.ok || !result.session_id) {
          const err =
            result.message || result.output || result.error || `Could not start ${row.label} OAuth`
          setStatus('error')
          setMessage(err)
          onError?.(err)
          return
        }
        setVerificationUri(result.verification_uri ?? null)
        setUserCode(result.user_code ?? null)
        setStatus(result.status === 'connected' ? 'connected' : 'pending')
        if (result.status === 'connected') {
          setMessage(`${row.label} is connected.`)
          onConnected?.()
          return
        }
        pollRef.current = window.setInterval(() => {
          void workframeAuthApi
            .providerOAuthStatus(row.id, result.session_id!)
            .then((poll) => {
              if (cancelled) return
              if (poll.verification_uri) setVerificationUri(poll.verification_uri)
              if (poll.user_code) setUserCode(poll.user_code)
              if (poll.status === 'connected' && poll.ok) {
                clearPoll()
                setStatus('connected')
                setMessage(`${row.label} is connected. You can close this dialog.`)
                onConnected?.()
                return
              }
              if (poll.status === 'error' || poll.ok === false) {
                clearPoll()
                const err = poll.message || poll.error || `${row.label} OAuth failed`
                setStatus('error')
                setMessage(err)
                onError?.(err)
              }
            })
            .catch((err: unknown) => {
              if (cancelled) return
              clearPoll()
              const errMsg = err instanceof Error ? err.message : `${row.label} OAuth failed`
              setStatus('error')
              setMessage(errMsg)
              onError?.(errMsg)
            })
        }, 2000)
      } catch (err) {
        if (cancelled) return
        const errMsg = err instanceof Error ? err.message : `Failed to start ${row.label} OAuth`
        setStatus('error')
        setMessage(errMsg)
        onError?.(errMsg)
      }
    })()

    return () => {
      cancelled = true
      clearPoll()
    }
  }, [clearPoll, onConnected, onError, open, reset, row, workspaceId])

  const copyCode = async () => {
    if (!userCode) return
    try {
      await navigator.clipboard.writeText(userCode)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      onError?.('Could not copy code to clipboard')
    }
  }

  if (!row) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="wf-dialog-content--narrow">
        <DialogHeader>
          <DialogTitle>Connect {row.label}</DialogTitle>
          <DialogDescription>
            Sign in with your {row.label} account using the device code flow. Keep this dialog open until
            connection completes.
          </DialogDescription>
        </DialogHeader>

        <div className="wf-device-oauth">
          {status === 'starting' ? (
            <p className="wf-user-settings__hint">Starting OAuth…</p>
          ) : null}

          {verificationUri ? (
            <div className="wf-dialog-field">
              <p className="wf-dialog-field__label-row">
                <strong>1. Open this link</strong>
              </p>
              <Button type="button" variant="outline" size="sm" asChild>
                <a href={verificationUri} target="_blank" rel="noreferrer">
                  Open sign-in page
                </a>
              </Button>
              <p className="wf-dialog-field__hint wf-device-oauth__uri">{verificationUri}</p>
            </div>
          ) : status === 'pending' ? (
            <p className="wf-user-settings__hint">Waiting for device code from Hermes…</p>
          ) : null}

          {userCode ? (
            <div className="wf-dialog-field">
              <p className="wf-dialog-field__label-row">
                <strong>2. Enter this code</strong>
              </p>
              <div className="wf-device-oauth__code-row">
                <code className="wf-device-oauth__code">{userCode}</code>
                <Button type="button" size="sm" variant="outline" onClick={() => void copyCode()}>
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </div>
            </div>
          ) : null}

          {status === 'pending' ? (
            <p className="wf-user-settings__hint">Waiting for sign-in… this window updates automatically.</p>
          ) : null}

          {status === 'connected' ? (
            <p className="wf-user-settings__hint">Connected. You can close this dialog.</p>
          ) : null}

          {status === 'error' && message ? (
            <p className="wf-connect-panel__hint wf-connect-panel__hint--security">{message}</p>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {status === 'connected' ? 'Done' : 'Cancel'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
