import { useCallback, useEffect, useState } from 'react'

import { PanelStatus } from '@/components/ui/PanelPrimitives'
import { SecretInput } from '@/components/ui/SecretInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type SmtpSettingsFieldsProps = {
  disabled?: boolean
  onBindSave?: (save: () => Promise<boolean>) => void
  onError?: (message: string) => void
}

export function SmtpSettingsFields({ disabled, onBindSave, onError }: SmtpSettingsFieldsProps) {
  const [host, setHost] = useState('')
  const [port, setPort] = useState('587')
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [from, setFrom] = useState('')
  const [hasPassword, setHasPassword] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const cfg = await workframeAuthApi.getInstallStack()
      const smtp = cfg.smtp
      if (smtp?.host) setHost(smtp.host)
      setPort(String(smtp?.port || 587))
      if (smtp?.user) setUser(smtp.user)
      if (smtp?.from) setFrom(smtp.from)
      setHasPassword(Boolean(smtp?.has_password))
      setPass('')
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Failed to load SMTP settings')
    } finally {
      setLoading(false)
    }
  }, [onError])

  useEffect(() => {
    void load()
  }, [load])

  const save = useCallback(async (): Promise<boolean> => {
    onError?.('')
    try {
      await workframeAuthApi.patchInstallStack({
        smtp: {
          host: host.trim(),
          port: Number(port) || 587,
          user: user.trim(),
          from: from.trim(),
          ...(pass.trim() ? { password: pass.trim() } : {}),
        },
      })
      setPass('')
      await load()
      return true
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Failed to save SMTP settings')
      return false
    }
  }, [from, host, load, onError, pass, port, user])

  useEffect(() => {
    onBindSave?.(save)
  }, [onBindSave, save])

  if (loading) {
    return <PanelStatus>Loading email delivery…</PanelStatus>
  }

  return (
    <div className="wf-onboarding-form">
      <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
        <div className="wf-dialog-field">
          <Label htmlFor="wf-smtp-settings-host">SMTP host</Label>
          <Input
            id="wf-smtp-settings-host"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="smtp.sendgrid.net"
            disabled={disabled}
          />
        </div>
        <div className="wf-dialog-field">
          <div className="wf-dialog-field__label-row">
            <Label htmlFor="wf-smtp-settings-port">Port</Label>
            <span className="wf-dialog-field__hint wf-dialog-field__hint--inline">
              465 SSL · 587 STARTTLS
            </span>
          </div>
          <Input
            id="wf-smtp-settings-port"
            value={port}
            onChange={(e) => setPort(e.target.value)}
            placeholder="587"
            disabled={disabled}
          />
        </div>
      </div>
      <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
        <div className="wf-dialog-field">
          <Label htmlFor="wf-smtp-settings-user">Username</Label>
          <Input
            id="wf-smtp-settings-user"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-smtp-settings-pass">Password</Label>
          <SecretInput
            id="wf-smtp-settings-pass"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            saved={hasPassword}
            emptyPlaceholder="SMTP password or API key"
            disabled={disabled}
          />
        </div>
      </div>
      <div className="wf-dialog-field">
        <Label htmlFor="wf-smtp-settings-from">From address</Label>
        <Input
          id="wf-smtp-settings-from"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          placeholder={user || 'same as username'}
          disabled={disabled}
        />
        <p className="wf-dialog-field__hint">Leave blank to use the login email as the sender.</p>
      </div>
    </div>
  )
}
