import { useEffect, useMemo, useState } from 'react'
import { LogOut, Save } from 'lucide-react'

import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { Button } from '@/components/ui/button'
import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import { PlatformIdentityPanel } from '@/components/settings/PlatformIdentityPanel'
import { ProviderConnectPanel } from '@/components/workspace/ProviderConnectPanel'
import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { AgentDelegationPanel } from '@/components/workspace/AgentDelegationPanel'
import { ThemeSettingsPanel } from '@/components/settings/ThemeSettingsPanel'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { userAvatarPersistPayload, userAvatarPickerValue } from '@/lib/presetAssets'
import { workframeAuthApi, type SessionProfile, type WorkspaceMember } from '@/lib/workframeAuthApi'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'

type ProfileTab = 'profile' | 'connect' | 'agents' | 'appearance'
type ConnectTab = 'providers' | 'models' | 'messaging'

type UserProfileSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialTab?: ProfileTab
  initialConnectTab?: ConnectTab
}

export function UserProfileSheet({
  open,
  onOpenChange,
  initialTab = 'profile',
  initialConnectTab = 'providers',
}: UserProfileSheetProps) {
  const { onLogout } = useWorkspacePanels()
  const [tab, setTab] = useState<ProfileTab>('profile')
  const [connectTab, setConnectTab] = useState<ConnectTab>('providers')
  const [profile, setProfile] = useState<SessionProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const [displayName, setDisplayName] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [tagline, setTagline] = useState('')
  const [bio, setBio] = useState('')
  const [workspaceMembers, setWorkspaceMembers] = useState<WorkspaceMember[]>([])

  useEffect(() => {
    if (!open) return
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')
      setStatus('')
      setTab(initialTab)
      if (initialTab === 'connect') setConnectTab(initialConnectTab)
      try {
        const me = await workframeAuthApi.getMe()
        if (cancelled) return
        setProfile(me)
        setDisplayName(me.user.display_name ?? '')
        setAvatarUrl(userAvatarPickerValue(me.user.avatar_url ?? ''))
        setTagline(me.user.tagline ?? '')
        setBio(me.user.bio ?? '')
        const workspaceId = me.current_workspace?.id ?? me.default_workspace?.id ?? ''
        if (workspaceId) {
          try {
            const memberList = await workframeAuthApi.listWorkspaceMembers(workspaceId)
            if (!cancelled) setWorkspaceMembers(memberList.members ?? [])
          } catch {
            if (!cancelled) setWorkspaceMembers([])
          }
        } else if (!cancelled) {
          setWorkspaceMembers([])
        }
      } catch (err) {
        if (!cancelled) {
          setError(formatWorkframeErrorMessage(err, 'Load profile'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [open, initialTab, initialConnectTab])

  const summary = useMemo(() => {
    if (!profile) return ''
    return profile.user.email?.trim() || ''
  }, [profile])

  const avatarDisplayUrl = useMemo(
    () => avatarUrl || resolveUserAvatarUrl(profile?.user.avatar_url),
    [avatarUrl, profile?.user.avatar_url],
  )

  const profileFieldsDisabled = loading || savingProfile

  const saveProfile = async () => {
    setError('')
    setSavingProfile(true)
    setStatus('Saving profile…')
    try {
      const avatar = avatarUrl ? userAvatarPersistPayload(avatarUrl) : null
      const result = await workframeAuthApi.updateMe({
        display_name: displayName,
        ...(avatar ?? {}),
        tagline,
        bio,
      })
      setProfile(result)
      setAvatarUrl(userAvatarPickerValue(result.user.avatar_url ?? avatarUrl))
      setStatus('Profile saved.')
    } catch (err) {
      setStatus('')
      setError(formatWorkframeErrorMessage(err, 'Save profile'))
    } finally {
      setSavingProfile(false)
    }
  }

  const handleLogout = async () => {
    if (!onLogout || loggingOut) return
    setLoggingOut(true)
    try {
      await onLogout()
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <SettingsSheetFrame
      open={open}
      onClose={() => onOpenChange(false)}
      title="Settings"
      summary={summary || undefined}
      titleId="wf-user-profile-title"
      loading={loading}
      tabs={[
        { id: 'profile', label: 'Identity & Bio' },
        { id: 'connect', label: 'Connected Accounts' },
        { id: 'agents', label: 'My Agents' },
        { id: 'appearance', label: 'Appearance' },
      ]}
      activeTab={tab}
      onTabChange={(next) => setTab(next as ProfileTab)}
      footer={
        onLogout ? (
          <Button
            type="button"
            variant="outline"
            className="w-full justify-start gap-2"
            disabled={loggingOut}
            onClick={() => void handleLogout()}
          >
            <LogOut className="w-4 h-4" aria-hidden="true" />
            {loggingOut ? 'Signing out…' : 'Log out'}
          </Button>
        ) : null
      }
    >
      <div className="space-y-6">
        {tab === 'agents' && error ? <WorkframeNotice message={error} /> : null}
        {tab === 'agents' && status ? <WorkframeStatusNotice message={status} /> : null}

        {tab === 'profile' ? (
          <div className="space-y-4" role="tabpanel">
            <div className="flex items-center justify-end gap-3">
              <Button
                type="button"
                variant="default"
                onClick={() => void saveProfile()}
                disabled={profileFieldsDisabled}
              >
                <Save className="w-4 h-4 mr-2" aria-hidden="true" />
                {savingProfile ? 'Saving…' : 'Save changes'}
              </Button>
            </div>

            {error ? <WorkframeNotice message={error} /> : null}
            {status ? <WorkframeStatusNotice message={status} /> : null}

            <div className="wf-wizard-panel wf-onboarding-form">
              <OnboardingIdentityFields
                avatarKind="user"
                avatarUrl={avatarDisplayUrl}
                onAvatarChange={setAvatarUrl}
                disabled={profileFieldsDisabled}
                primary={{
                  id: 'wf-settings-profile-name',
                  label: 'Display name',
                  value: displayName,
                  onChange: setDisplayName,
                }}
                secondary={{
                  id: 'wf-settings-profile-tag',
                  label: 'Tagline',
                  value: tagline,
                  onChange: setTagline,
                }}
                body={{
                  id: 'wf-settings-profile-bio',
                  label: 'About you',
                  value: bio,
                  onChange: setBio,
                  rows: 3,
                }}
              />
            </div>
          </div>
        ) : tab === 'connect' ? (
          <div className="space-y-4" role="tabpanel">
            {error ? <WorkframeNotice message={error} /> : null}
            {status ? <WorkframeStatusNotice message={status} /> : null}

            <div className="wf-wizard-panel wf-onboarding-form">
              <div className="wf-wizard-subtabs" role="tablist" aria-label="Connected account sections">
                {(
                  [
                    ['providers', 'LLM Providers'],
                    ['models', 'LLM Models'],
                    ['messaging', 'Messaging'],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={connectTab === id}
                    className={`wf-wizard-subtabs__btn${connectTab === id ? ' is-active' : ''}`}
                    onClick={() => setConnectTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {connectTab === 'providers' ? (
                <ProviderConnectPanel
                  disabled={loading}
                  workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id}
                  credentialScope="user"
                  categories={['llm', 'dev', 'search']}
                  hint="none"
                  layout="stack"
                  onStatus={setStatus}
                  onError={setError}
                />
              ) : null}

              {connectTab === 'messaging' ? (
                <PlatformIdentityPanel
                  embedded
                  workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id}
                  disabled={loading}
                  onLinked={() => setStatus('Messaging account linked.')}
                />
              ) : null}

              {connectTab === 'models' ? (
                <ModelPickerPanel
                  embedded
                  workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id}
                  onError={setError}
                />
              ) : null}
            </div>
          </div>
        ) : tab === 'agents' ? (
          <div className="space-y-6" role="tabpanel">
            <AgentDelegationPanel
              workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id ?? ''}
              currentUserId={profile?.user.user_id ?? ''}
              members={workspaceMembers}
              loading={loading}
            />
          </div>
        ) : (
          <ThemeSettingsPanel />
        )}
      </div>
    </SettingsSheetFrame>
  )
}
