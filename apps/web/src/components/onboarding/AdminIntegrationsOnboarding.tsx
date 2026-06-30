import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type AdminIntegrationsOnboardingProps = {
  workspaceId: string
  onComplete: () => void
}

export function AdminIntegrationsOnboarding({ workspaceId, onComplete }: AdminIntegrationsOnboardingProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [githubClientId, setGithubClientId] = useState('')
  const [githubClientSecret, setGithubClientSecret] = useState('')

  const appBase = useMemo(() => {
    const base = import.meta.env.VITE_APP_BASE_URL || window.location.origin
    return base.replace(/\/$/, '')
  }, [])

  const callbackUrl = useMemo(() => `${appBase}/api/oauth/github/callback`, [appBase])

  const loadWorkspace = useCallback(async () => {
    if (!workspaceId) return
    try {
      const detail = await workframeAuthApi.getWorkspace(workspaceId)
      setGithubClientId(detail.workspace.integrations?.github_oauth_client_id ?? '')
    } catch {
      // optional prefill
    }
  }, [workspaceId])

  useEffect(() => {
    void loadWorkspace()
  }, [loadWorkspace])

  async function saveAndContinue(skipKeys = false) {
    setBusy(true)
    setError(null)
    try {
      const id = githubClientId.trim()
      const secret = githubClientSecret.trim()
      if (!skipKeys && (id || secret)) {
        await workframeAuthApi.patchWorkspaceIntegrations(workspaceId, {
          github_oauth_client_id: id,
          github_oauth_client_secret: secret || undefined,
        })
      }
      await workframeAuthApi.patchWorkspaceIntegrations(workspaceId, {
        admin_integrations_done: true,
      })
      onComplete()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save workspace integrations'))
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      {error ? <WorkframeNotice message={error} className="mb-1" /> : null}

      <p className="text-sm text-muted-foreground">
        <a
          className="text-primary underline"
          href="https://github.com/settings/developers"
          target="_blank"
          rel="noreferrer"
        >
          New GitHub OAuth app
        </a>
        {' — paste the two URLs below, then drop the client ID and secret here.'}
      </p>

      <div className="space-y-3">
        <div className="wf-dialog-field">
          <Label htmlFor="wf-onboard-gh-home">Homepage URL</Label>
          <Input id="wf-onboard-gh-home" readOnly value={appBase} />
        </div>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-onboard-gh-callback">Authorization callback URL</Label>
          <Input id="wf-onboard-gh-callback" readOnly value={callbackUrl} />
        </div>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-onboard-gh-id">Client ID</Label>
          <Input
            id="wf-onboard-gh-id"
            value={githubClientId}
            onChange={(event) => setGithubClientId(event.target.value)}
            placeholder="Ov23li…"
            disabled={busy}
          />
        </div>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-onboard-gh-secret">Client secret</Label>
          <Input
            id="wf-onboard-gh-secret"
            type="password"
            value={githubClientSecret}
            onChange={(event) => setGithubClientSecret(event.target.value)}
            placeholder="Leave blank to keep existing"
            disabled={busy}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 justify-end pt-1">
        <Button type="button" variant="outline" disabled={busy} onClick={() => void saveAndContinue(true)}>
          Skip
        </Button>
        <Button type="button" disabled={busy} onClick={() => void saveAndContinue(false)}>
          Continue
        </Button>
      </div>
    </div>
  )
}
