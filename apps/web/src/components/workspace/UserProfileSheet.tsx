import { useEffect, useMemo, useState } from 'react'
import { LogOut, Save } from 'lucide-react'

import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { WfActionButton } from '@/components/ui/WfActionButton'
import { PlatformIdentityPanel } from '@/components/settings/PlatformIdentityPanel'
import { ProviderConnectPanel } from '@/components/workspace/ProviderConnectPanel'
import { AgentDelegationPanel } from '@/components/workspace/AgentDelegationPanel'
import { ThemeSettingsPanel } from '@/components/settings/ThemeSettingsPanel'
import { SettingsPanelBody } from '@/components/workspace/SettingsPanelBody'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { userAvatarPersistPayload, userAvatarPickerValue } from '@/lib/presetAssets'
import { workframeAuthApi, type SessionProfile, type WorkspaceMember } from '@/lib/workframeAuthApi'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'

type ProfileTab = 'profile' | 'connect' | 'agents' | 'appearance'
type ConnectTab = 'providers' | 'messaging'

type UserProfileSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialTab?: ProfileTab
  initialConnectTab?: ConnectTab | 'models'
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
    setTab(initialTab)
    if (initialTab === 'connect') {
      setConnectTab(initialConnectTab === 'messaging' ? 'messaging' : 'providers')
    }
    setError('')
    setStatus('')
  }, [open, initialTab, initialConnectTab])

  useEffect(() => {
    if (!open) return
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')
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
  }, [open])

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
      setStatus('Profile saved. Your identity updates are live.')
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
      contentFill={false}
      tabs={[
        { id: 'profile', label: 'Identity & Bio' },
        { id: 'connect', label: 'Connected Accounts' },
        { id: 'agents', label: 'My Agents' },
        { id: 'appearance', label: 'Appearance' },
      ]}
      activeTab={tab}
      onTabChange={(next) => setTab(next as ProfileTab)}
      actions={
        tab === 'profile' ? (
          <WfActionButton
            type="button"
            tone="primary"
            onClick={() => void saveProfile()}
            disabled={profileFieldsDisabled}
          >
            <Save className="w-4 h-4 mr-2" aria-hidden="true" />
            {savingProfile ? 'Saving…' : 'Save changes'}
          </WfActionButton>
        ) : null
      }
      footer={
        onLogout ? (
          <WfActionButton
            type="button"
            className="w-full justify-start gap-2"
            disabled={loggingOut}
            onClick={() => void handleLogout()}
          >
            <LogOut className="w-4 h-4" aria-hidden="true" />
            {loggingOut ? 'Signing out…' : 'Log out'}
          </WfActionButton>
        ) : null
      }
    >
      <div className="space-y-6">
        {tab === 'profile' ? (
          <SettingsPanelBody error={error} status={status}>
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
          </SettingsPanelBody>
        ) : tab === 'connect' ? (
          <SettingsPanelBody
            error={error}
            status={status}
            tabs={[
              { id: 'providers', label: 'Integrations' },
              { id: 'messaging', label: 'Linked accounts' },
            ]}
            activeTab={connectTab}
            onTabChange={(id) => setConnectTab(id as ConnectTab)}
            tablistLabel="Model keys sections"
          >
            {connectTab === 'providers' ? (
              <ProviderConnectPanel
                  disabled={loading}
                  workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id}
                  credentialScope="user"
                  categories={['llm', 'dev', 'search']}
                  hint="none"
                  layout="stack"
                  deviceOAuthPresentation="inline"
                  onError={(message) => {
                    setError(message)
                    setStatus('')
                  }}
                  onStatus={(message) => {
                    setError('')
                    setStatus(message)
                  }}
                  onConnected={() => {
                    setStatus('Provider connected. Choose a model per agent in Agent Settings.')
                  }}
                />
              ) : null}

            {connectTab === 'messaging' ? (
              <PlatformIdentityPanel
                embedded
                workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id}
                disabled={loading}
                onLinked={() => setStatus('Account linked.')}
              />
            ) : null}
          </SettingsPanelBody>
        ) : tab === 'agents' ? (
          <SettingsPanelBody error={error} status={status}>
            <AgentDelegationPanel
              workspaceId={profile?.current_workspace?.id ?? profile?.default_workspace?.id ?? ''}
              currentUserId={profile?.user.user_id ?? ''}
              members={workspaceMembers}
              loading={loading}
            />
          </SettingsPanelBody>
        ) : (
          <SettingsPanelBody>
            <ThemeSettingsPanel />
          </SettingsPanelBody>
        )}
      </div>
    </SettingsSheetFrame>
  )
}
