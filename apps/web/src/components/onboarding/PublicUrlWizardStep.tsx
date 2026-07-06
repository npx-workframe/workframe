import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi, type PublishHints } from '@/lib/workframeAuthApi'

type PublicUrlWizardStepProps = {
  publicUrl: string
  onPublicUrlChange: (value: string) => void
  disabled?: boolean
}

function hostFromPublicUrl(url: string): string {
  const trimmed = url.trim()
  if (!trimmed) return ''
  try {
    const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
    return new URL(withScheme).hostname
  } catch {
    return trimmed.replace(/^https?:\/\//i, '').split('/')[0] || ''
  }
}

function CopyField({
  label,
  value,
  fullWidth,
}: {
  label: string
  value: string
  fullWidth?: boolean
}) {
  const copy = useCallback(() => {
    void navigator.clipboard.writeText(value).catch(() => {})
  }, [value])

  return (
    <div className={`wf-sign-in-app__field${fullWidth ? ' wf-sign-in-app__field--full' : ''}`}>
      <Label>{label}</Label>
      <div className="wf-copy-field">
        <Input readOnly value={value} aria-label={label} />
        <Button type="button" variant="outline" size="sm" onClick={copy} disabled={!value}>
          Copy
        </Button>
      </div>
    </div>
  )
}

export function PublicUrlWizardStep({ publicUrl, onPublicUrlChange, disabled }: PublicUrlWizardStepProps) {
  const host = hostFromPublicUrl(publicUrl)
  const [hints, setHints] = useState<PublishHints | null>(null)
  const [httpsBusy, setHttpsBusy] = useState(false)
  const [httpsStatus, setHttpsStatus] = useState('')

  useEffect(() => {
    if (!host.trim()) {
      setHints(null)
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      void workframeAuthApi
        .getPublishHints(publicUrl)
        .then((data) => {
          if (!cancelled) setHints(data)
        })
        .catch(() => {
          if (!cancelled) setHints(null)
        })
    }, 300)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [publicUrl, host])

  const dnsName = hints?.dns.name || (host.includes('.') ? host.split('.')[0] : '@')
  const serverIp = hints?.public_ipv4 || '…'
  const setupCommand =
    hints?.setup_command ||
    `sudo bash /opt/workframe/scripts/workframe/setup-public-https.sh ${host || 'your.domain.com'} ${hints?.ui_port ?? 28644}`
  const godaddy =
    hints?.registrar_links.find((l) => l.label.includes('GoDaddy'))?.url ||
    'https://dcc.godaddy.com/control/portfolio'

  async function setupHttpsOnServer() {
    if (!host.trim()) return
    setHttpsBusy(true)
    setHttpsStatus('')
    try {
      const result = await workframeAuthApi.setupPublicHttps(publicUrl)
      if (result.ok) {
        setHttpsStatus('HTTPS installed. The certificate will activate once DNS points to this server.')
      } else {
        setHttpsStatus(formatWorkframeErrorMessage(result.error || 'HTTPS setup failed'))
      }
    } catch (err) {
      setHttpsStatus(formatWorkframeErrorMessage(err, 'HTTPS setup'))
    } finally {
      setHttpsBusy(false)
    }
  }

  return (
    <div className="wf-wizard-panel wf-onboarding-form">
      <div className="wf-dialog-field">
        <Label htmlFor="wf-publish-url">Public domain</Label>
        <Input
          id="wf-publish-url"
          value={publicUrl}
          onChange={(e) => onPublicUrlChange(e.target.value)}
          placeholder="dev.example.com"
          disabled={disabled}
        />
      </div>

      {host ? (
        <div className="wf-publish-setup">
          <details className="wf-publish-card" open>
            <summary className="wf-publish-card__title">1 — DNS</summary>
            <div className="wf-publish-card__body">
              <p className="wf-publish-card__lede">
                <a className="text-primary underline" href={godaddy} target="_blank" rel="noreferrer">
                  Open DNS
                </a>
                {hints?.apex_domain ? ` (${hints.apex_domain})` : ''} — A record for <code>{host}</code>:
              </p>
              <div className="wf-sign-in-app__grid">
                <CopyField label="Type" value="A" />
                <CopyField label="Name" value={dnsName} />
                <CopyField label="Value" value={serverIp} fullWidth />
              </div>
              {hints?.dns_cname ? (
                <details className="wf-publish-nested">
                  <summary>CNAME instead (optional)</summary>
                  <div className="wf-sign-in-app__grid wf-mt-2">
                    <CopyField label="Type" value="CNAME" />
                    <CopyField label="Name" value={hints.dns_cname.name} />
                    <CopyField label="Value" value={hints.dns_cname.value} fullWidth />
                  </div>
                </details>
              ) : null}
              {hints?.registrar_links && hints.registrar_links.length > 1 ? (
                <p className="wf-publish-card__links">
                  {hints.registrar_links
                    .filter((l) => !l.label.includes('GoDaddy'))
                    .map((link, i) => (
                      <span key={link.url}>
                        {i > 0 ? ' · ' : ''}
                        <a className="text-primary underline" href={link.url} target="_blank" rel="noreferrer">
                          {link.label}
                        </a>
                      </span>
                    ))}
                </p>
              ) : null}
            </div>
          </details>

          <details className="wf-publish-card" open>
            <summary className="wf-publish-card__title">2 — HTTPS</summary>
            <div className="wf-publish-card__body">
              <div className="wf-publish-card__actions">
                <Button type="button" disabled={disabled || httpsBusy || !host} onClick={() => void setupHttpsOnServer()}>
                  {httpsBusy ? 'Installing…' : 'Set up HTTPS'}
                </Button>
              </div>
              {httpsStatus ? <p className="wf-sign-in-app__hint">{httpsStatus}</p> : null}
              <CopyField label="SSH command" value={setupCommand} fullWidth />
            </div>
          </details>
        </div>
      ) : null}
    </div>
  )
}
