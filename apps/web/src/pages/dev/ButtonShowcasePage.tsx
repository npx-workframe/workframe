import type { ReactNode } from 'react'
import { Save } from 'lucide-react'

import { ThemeSwitcher } from '@/components/shell/ThemeSwitcher'
import { Button } from '@/components/ui/button'
import { WfActionButton } from '@/components/ui/WfActionButton'
import { useTheme } from '@/hooks/useTheme'

function SpecRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="wf-btn-showcase__row">
      <span className="wf-btn-showcase__label">{label}</span>
      <div className="wf-btn-showcase__samples">{children}</div>
    </div>
  )
}

function FooterMock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="wf-btn-showcase__footer-mock">
      <p className="wf-btn-showcase__footer-title">{title}</p>
      <footer className="wf-dialog-footer wf-btn-showcase__footer-bar">{children}</footer>
    </div>
  )
}

function RailMock() {
  return (
    <div className="wf-btn-showcase__rail-mock">
      <p className="wf-btn-showcase__footer-title">Wizard rail (nav items use same control tokens)</p>
      <div className="wf-btn-showcase__rail-inset wf-onboarding-wizard__nav">
        <ul className="wf-onboarding-wizard__steps">
          <li className="is-done is-clickable">
            <button type="button" className="wf-onboarding-wizard__step-btn">
              <span className="wf-onboarding-wizard__step-mark" aria-hidden="true">
                ✓
              </span>
              <span className="wf-onboarding-wizard__step-copy">
                <span className="wf-onboarding-wizard__step-label">Welcome</span>
              </span>
            </button>
          </li>
          <li className="is-current is-clickable">
            <button type="button" className="wf-onboarding-wizard__step-btn">
              <span className="wf-onboarding-wizard__step-mark" aria-hidden="true">
                2
              </span>
              <span className="wf-onboarding-wizard__step-copy">
                <span className="wf-onboarding-wizard__step-label">Deployment</span>
              </span>
            </button>
          </li>
          <li className="is-clickable">
            <button type="button" className="wf-onboarding-wizard__step-btn">
              <span className="wf-onboarding-wizard__step-mark" aria-hidden="true">
                3
              </span>
              <span className="wf-onboarding-wizard__step-copy">
                <span className="wf-onboarding-wizard__step-label">Email &amp; admin</span>
              </span>
            </button>
          </li>
          <li>
            <button type="button" className="wf-onboarding-wizard__step-btn is-static" disabled>
              <span className="wf-onboarding-wizard__step-mark" aria-hidden="true">
                ·
              </span>
              <span className="wf-onboarding-wizard__step-copy">
                <span className="wf-onboarding-wizard__step-label">Integrations</span>
              </span>
            </button>
          </li>
        </ul>
      </div>
      <p className="wf-btn-showcase__hint">
        Rail needs inline gutter + step gap so neo pop-up shadows are not clipped. Inactive future steps = low
        contrast, no hover pop-up.
      </p>
    </div>
  )
}

export function ButtonShowcasePage() {
  const { theme } = useTheme()

  return (
    <div className="wf-btn-showcase">
      <header className="wf-btn-showcase__header">
        <div>
          <p className="wf-btn-showcase__eyebrow">UI lab · /dev/buttons (or ?wf-dev=buttons)</p>
          <h1>Action button contract</h1>
          <p className="wf-btn-showcase__lede">
            Theme: <strong>{theme}</strong> — toggle to compare neo relief vs dark glass. Hover buttons to see
            default pop-up/fill. Primary stays raised/filled with no extra hover.
          </p>
        </div>
        <ThemeSwitcher />
      </header>

      <section className="wf-btn-showcase__card">
        <h2>Single tones</h2>
        <SpecRow label="Default (hover me)">
          <WfActionButton>Cancel</WfActionButton>
          <WfActionButton>Close</WfActionButton>
          <WfActionButton>Send test email</WfActionButton>
        </SpecRow>
        <SpecRow label="Inactive (no hover)">
          <WfActionButton tone="inactive">Continue to verification</WfActionButton>
          <WfActionButton tone="inactive" disabled>
            Disabled
          </WfActionButton>
        </SpecRow>
        <SpecRow label="Primary (stays up)">
          <WfActionButton tone="primary">
            <Save aria-hidden="true" />
            Save changes
          </WfActionButton>
          <WfActionButton tone="primary" wizardSize>
            Continue
          </WfActionButton>
          <WfActionButton tone="primary" wizardSize>
            Get started
          </WfActionButton>
        </SpecRow>
      </section>

      <section className="wf-btn-showcase__card">
        <h2>Wizard footer pairs</h2>
        <FooterMock title="SMTP not verified — test is the gate; Continue waits">
          <WfActionButton wizardSize tone="primary">
            Send test email
          </WfActionButton>
          <WfActionButton wizardSize tone="inactive">
            Continue to verification
          </WfActionButton>
        </FooterMock>
        <FooterMock title="SMTP verified — Continue is primary; test is optional default">
          <WfActionButton wizardSize>Send test email</WfActionButton>
          <WfActionButton wizardSize tone="primary">
            Continue
          </WfActionButton>
        </FooterMock>
        <FooterMock title="Settings / modal save">
          <WfActionButton>Close</WfActionButton>
          <WfActionButton tone="primary">
            <Save aria-hidden="true" />
            Save changes
          </WfActionButton>
        </FooterMock>
        <FooterMock title="Create / invite flows">
          <WfActionButton>Cancel</WfActionButton>
          <WfActionButton tone="primary">Create project</WfActionButton>
        </FooterMock>
        <FooterMock title="Invite">
          <WfActionButton>Close</WfActionButton>
          <WfActionButton tone="primary">Send invite</WfActionButton>
        </FooterMock>
      </section>

      <section className="wf-btn-showcase__card">
        <h2>Before → after (why grey Save goes away)</h2>
        <div className="wf-btn-showcase__compare">
          <div>
            <p className="wf-btn-showcase__footer-title">Legacy shadcn default (bg-primary fill)</p>
            <Button variant="default">Save changes</Button>
          </div>
          <div>
            <p className="wf-btn-showcase__footer-title">New wf-action-btn primary</p>
            <WfActionButton tone="primary">
              <Save aria-hidden="true" />
              Save changes
            </WfActionButton>
          </div>
        </div>
      </section>

      <section className="wf-btn-showcase__card">
        <RailMock />
      </section>

      <section className="wf-btn-showcase__card wf-btn-showcase__spec">
        <h2>Contract (what we will roll out)</h2>
        <div className="wf-btn-showcase__spec-grid">
          <div>
            <h3>Neo</h3>
            <ul>
              <li>Default: flush — no border, bg, or shadow</li>
              <li>Default hover: pop up (raised surface + relief shadow)</li>
              <li>Inactive: flush + low-contrast text; hover does nothing</li>
              <li>Primary / active: pop up by default; hover unchanged</li>
              <li>No 2px white borders on controls — only shell dividers</li>
            </ul>
          </div>
          <div>
            <h3>Dark</h3>
            <ul>
              <li>Default: 10% white border, no fill</li>
              <li>Default hover: 10% white fill; border width kept, color transparent</li>
              <li>Inactive: 5% border + muted text; no hover</li>
              <li>Primary / active: 10% white fill; border transparent; hover unchanged</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  )
}
