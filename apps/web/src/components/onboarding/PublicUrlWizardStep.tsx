import { useEffect, useState } from 'react'

import { CopyInput } from '@/components/ui/CopyInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi, type PublishHints } from '@/lib/workframeAuthApi'

type PublicUrlWizardStepProps = {
  publicUrl: string
  onPublicUrlChange: (value: string) => void
  disabled?: boolean
  httpsStatus?: string | null
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

export function PublicUrlWizardStep({
  publicUrl,
  onPublicUrlChange,
  disabled,
  httpsStatus,
}: PublicUrlWizardStepProps) {
  const host = hostFromPublicUrl(publicUrl)
  const [hints, setHints] = useState<PublishHints | null>(null)

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
  const registrarLinks = hints?.registrar_links ?? []

  return (
    <div className="wf-wizard-panel wf-onboarding-form wf-publish-step">
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
          <section className="wf-publish-section" aria-labelledby="wf-publish-dns-title">
            <header className="wf-publish-section__head">
              <h3 id="wf-publish-dns-title" className="wf-publish-section__title">
                1 — DNS
              </h3>
              <p className="wf-publish-section__lede">
                Add an <strong>A record</strong> at your registrar so <code>{host}</code> points at this
                server.
              </p>
            </header>

            <div className="wf-publish-dns-grid">
              <div className="wf-dialog-field wf-publish-dns-grid__type">
                <Label>Type</Label>
                <CopyInput value="A" mono={false} />
              </div>
              <div className="wf-dialog-field wf-publish-dns-grid__name">
                <Label>Name</Label>
                <CopyInput value={dnsName} />
              </div>
              <div className="wf-dialog-field wf-publish-dns-grid__value">
                <Label>Value (server IP)</Label>
                <CopyInput value={serverIp} />
              </div>
            </div>

            {registrarLinks.length ? (
              <div className="wf-publish-registrars">
                <span className="wf-publish-registrars__label">Open DNS at</span>
                <div className="wf-publish-registrars__links">
                  {registrarLinks.map((link) => (
                    <a
                      key={link.url}
                      className="wf-publish-registrars__link"
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            ) : (
              <p className="wf-publish-section__hint">
                Use your domain registrar&apos;s DNS panel to add the record above.
              </p>
            )}

            {hints?.dns_cname ? (
              <details className="wf-publish-alt">
                <summary>Use CNAME instead (optional)</summary>
                <div className="wf-publish-dns-grid wf-publish-alt__grid">
                  <div className="wf-dialog-field wf-publish-dns-grid__type">
                    <Label>Type</Label>
                    <CopyInput value="CNAME" mono={false} />
                  </div>
                  <div className="wf-dialog-field wf-publish-dns-grid__name">
                    <Label>Name</Label>
                    <CopyInput value={hints.dns_cname.name} />
                  </div>
                  <div className="wf-dialog-field wf-publish-dns-grid__value">
                    <Label>Target</Label>
                    <CopyInput value={hints.dns_cname.value} />
                  </div>
                </div>
              </details>
            ) : null}
          </section>

          <section className="wf-publish-section" aria-labelledby="wf-publish-https-title">
            <header className="wf-publish-section__head">
              <h3 id="wf-publish-https-title" className="wf-publish-section__title">
                2 — HTTPS
              </h3>
              <p className="wf-publish-section__lede">
                After DNS propagates, run <strong>Set up HTTPS</strong> below (or use the SSH command if you
                prefer the shell).
              </p>
            </header>

            {httpsStatus ? (
              <WorkframeNotice
                message={httpsStatus}
                tone={/installed|activated/i.test(httpsStatus) ? 'info' : 'caution'}
                className="wf-notice--wizard"
              />
            ) : null}

            <div className="wf-dialog-field">
              <Label>SSH command</Label>
              <CopyInput value={setupCommand} />
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}

export async function runPublicHttpsSetup(publicUrl: string): Promise<string> {
  if (!publicUrl.trim()) return ''
  try {
    const result = await workframeAuthApi.setupPublicHttps(publicUrl)
    if (result.ok) {
      return 'HTTPS installed. The certificate will activate once DNS points to this server.'
    }
    return formatWorkframeErrorMessage(result.error || 'HTTPS setup failed', 'HTTPS setup')
  } catch (err) {
    return formatWorkframeErrorMessage(err, 'HTTPS setup')
  }
}
