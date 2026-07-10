import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Save } from 'lucide-react'

import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { AdminOAuthSetup } from '@/components/onboarding/AdminOAuthSetup'
import { AdminStripeSetup } from '@/components/onboarding/AdminStripeSetup'
import { WorkspaceMessagingPanel } from '@/components/onboarding/WorkspaceMessagingPanel'
import { SiteBrandingFields } from '@/components/settings/SiteBrandingFields'
import { SettingsSection } from '@/components/settings/SettingsSection'
import { SmtpSettingsFields } from '@/components/settings/SmtpSettingsFields'
import { WfActionButton } from '@/components/ui/WfActionButton'
import { Button } from '@/components/ui/button'
import { ReducedProfileCard } from '@/components/ui/ReducedProfileCard'
import { SettingsPanelBody } from '@/components/workspace/SettingsPanelBody'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { AgentDelegationPanel } from '@/components/workspace/AgentDelegationPanel'
import { StackUpdatesPanel } from '@/components/workspace/StackUpdatesPanel'
import { resolveLogoUrl, resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { logoAvatarPersistPayload, logoAvatarPickerValue } from '@/lib/presetAssets'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import {
  workframeAuthApi,
  type WorkspaceDetail,
  type WorkspaceInvite,
  type WorkspaceMember,
} from '@/lib/workframeAuthApi'

type WorkframeSettingsSheetProps = {
  open: boolean
  onClose: () => void
  workspaceId: string
  workspaceSlug?: string
  currentUserId: string
  canManage: boolean
  onInviteClick: () => void
  onChanged?: () => void
}

type WorkframeTab = 'workframe' | 'members' | 'invites' | 'integrations' | 'delegation' | 'updates'

export function WorkframeSettingsSheet({
  open,
  onClose,
  workspaceId,
  workspaceSlug,
  currentUserId,
  canManage,
  onInviteClick,
  onChanged,
}: WorkframeSettingsSheetProps) {
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null)
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [invites, setInvites] = useState<WorkspaceInvite[]>([])
  const [displayName, setDisplayName] = useState('')
  const [workframeTagline, setWorkframeTagline] = useState('')
  const [description, setDescription] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [tab, setTab] = useState<WorkframeTab>('workframe')
  const [loading, setLoading] = useState(false)
  const [busyUserId, setBusyUserId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [updatesBadge, setUpdatesBadge] = useState(0)
  const oauthSaveRef = useRef<(() => Promise<boolean>) | null>(null)
  const stripeSaveRef = useRef<(() => Promise<boolean>) | null>(null)
  const messagingSaveRef = useRef<(() => Promise<boolean>) | null>(null)
  const smtpSaveRef = useRef<(() => Promise<boolean>) | null>(null)

  const load = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    setError('')
    try {
      const [detail, memberList, inviteList] = await Promise.all([
        workframeAuthApi.getWorkspace(workspaceId),
        workframeAuthApi.listWorkspaceMembers(workspaceId),
        canManage
          ? workframeAuthApi.listWorkspaceInvites(workspaceId)
          : Promise.resolve({ invites: [] as WorkspaceInvite[] }),
      ])
      setWorkspace(detail.workspace)
      setMembers(memberList.members ?? [])
      setInvites(inviteList.invites ?? [])
      setDisplayName(detail.workspace.display_name ?? '')
      setWorkframeTagline(detail.workspace.tagline ?? '')
      setDescription(detail.workspace.description ?? '')
      setAvatarUrl(logoAvatarPickerValue(detail.workspace.avatar_url ?? ''))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load Workframe settings')
    } finally {
      setLoading(false)
    }
  }, [canManage, workspaceId])

  useEffect(() => {
    if (!open) return
    setTab('workframe')
    setError('')
    setStatus('')
  }, [open])

  useEffect(() => {
    if (!open) return
    void load()
  }, [load, open])

  useEffect(() => {
    if (!open || !canManage) {
      setUpdatesBadge(0)
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const bridge = (window as Window & { workframe?: { getAppVersion?: () => Promise<string> } }).workframe
        const desktopVersion = bridge?.getAppVersion ? await bridge.getAppVersion().catch(() => '') : ''
        const status = await workframeAuthApi.getAdminUpdates(desktopVersion || undefined)
        if (cancelled) return
        let count = 0
        if (status.workframe?.update_available) count += 1
        if (status.hermes?.update_available) count += 1
        if (status.desktop?.update_available) count += 1
        setUpdatesBadge(count)
      } catch {
        if (!cancelled) setUpdatesBadge(0)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [canManage, open])

  const pendingInvites = useMemo(
    () => invites.filter((invite) => !invite.accepted_at),
    [invites],
  )

  const headerSlug = workspace?.slug || workspaceSlug || 'workframe'

  const avatarDisplayUrl = useMemo(() => {
    return resolveLogoUrl(avatarUrl || workspace?.avatar_url, DEFAULT_WORKSPACE_LOGO)
  }, [avatarUrl, workspace?.avatar_url])

  const fieldsDisabled = loading || saving || !canManage

  const saveWorkframe = async () => {
    if (!workspaceId) return
    setSaving(true)
    setError('')
    setStatus('')
    try {
      const logo = avatarUrl ? logoAvatarPersistPayload(avatarUrl) : null
      const result = await workframeAuthApi.patchWorkspace(workspaceId, {
        display_name: displayName,
        description,
        tagline: workframeTagline,
        ...(logo ?? {}),
      })
      setWorkspace(result.workspace)
      setStatus('Workframe profile saved.')
      onChanged?.()
      await load()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save workframe'))
    } finally {
      setSaving(false)
    }
  }

  const saveIntegrations = async () => {
    if (!canManage || !workspaceId) return
    setSaving(true)
    setError('')
    setStatus('')
    try {
      const results = await Promise.all([
        stripeSaveRef.current?.() ?? Promise.resolve(true),
        oauthSaveRef.current?.() ?? Promise.resolve(true),
        messagingSaveRef.current?.() ?? Promise.resolve(true),
        smtpSaveRef.current?.() ?? Promise.resolve(true),
      ])
      if (results.some((ok) => !ok)) {
        return
      }
      setStatus('Integrations saved. Changes apply on the next agent run.')
      await load()
      onChanged?.()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save integrations'))
    } finally {
      setSaving(false)
    }
  }

  const removeMember = async (member: WorkspaceMember) => {
    if (!canManage || !workspaceId || member.user_id === currentUserId) return
    setBusyUserId(member.user_id)
    setError('')
    setStatus('')
    try {
      await workframeAuthApi.removeWorkspaceMember(workspaceId, member.user_id)
      setStatus(`Removed ${member.display_name || member.email || member.user_id}.`)
      await load()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove member')
    } finally {
      setBusyUserId('')
    }
  }

  return (
    <SettingsSheetFrame
      open={open}
      onClose={onClose}
      title="Workframe Settings"
      summary={tab === 'workframe' ? `@${headerSlug}` : undefined}
      titleId="wf-team-settings-title"
      loading={loading}
      tabs={[
        { id: 'workframe', label: 'Identity & Bio' },
        { id: 'members', label: 'Members' },
        { id: 'delegation', label: 'Delegation' },
        ...(canManage
          ? [
              {
                id: 'updates',
                label: updatesBadge > 0 ? `Updates (${updatesBadge})` : 'Updates',
              },
              { id: 'invites', label: 'Invites' },
              { id: 'integrations', label: 'Integrations' },
            ]
          : []),
      ]}
      activeTab={tab}
      onTabChange={(next) => setTab(next as WorkframeTab)}
      actions={
        tab === 'workframe' && canManage ? (
          <WfActionButton
            type="button"
            tone="primary"
            onClick={() => void saveWorkframe()}
            disabled={fieldsDisabled}
          >
            <Save className="w-4 h-4 mr-2" aria-hidden="true" />
            {saving ? 'Saving…' : 'Save changes'}
          </WfActionButton>
        ) : null
      }
      footer={
        <p className="wf-user-settings__hint m-0">Workframe ID: {workspaceId}</p>
      }
    >
      <div className="wf-workframe-settings space-y-4">
        {tab === 'workframe' ? (
          <SettingsPanelBody error={error} status={status}>
            <OnboardingIdentityFields
              avatarKind="logo"
              avatarLabel="Logo"
              avatarUrl={avatarDisplayUrl}
              onAvatarChange={setAvatarUrl}
              disabled={fieldsDisabled}
              primary={{
                id: 'wf-workframe-name',
                label: 'Workframe name',
                value: displayName,
                onChange: setDisplayName,
              }}
              secondary={{
                id: 'wf-workframe-tagline',
                label: 'Tagline',
                value: workframeTagline,
                onChange: setWorkframeTagline,
              }}
              body={{
                id: 'wf-workframe-description',
                label: 'Mission',
                value: description,
                onChange: setDescription,
                rows: 4,
                placeholder: 'What this Workframe is for',
              }}
            />

            {canManage ? (
              <SettingsSection
                title="Web presence"
                hint="Link previews, PWA install name, favicon, and theme color for this Workframe."
              >
                <SiteBrandingFields disabled={fieldsDisabled} onStatus={setStatus} />
              </SettingsSection>
            ) : null}

            {!canManage ? (
              <p className="wf-user-settings__hint">Only a Workframe admin can edit these details.</p>
            ) : null}
          </SettingsPanelBody>
        ) : null}

        {tab === 'members' ? (
          <div className="space-y-4">
            {canManage ? (
              <div className="flex items-center justify-end gap-3">
                <WfActionButton type="button" tone="primary" onClick={onInviteClick}>
                  Invite member
                </WfActionButton>
              </div>
            ) : null}

            <SettingsPanelBody error={error} status={status} bare>
              {members.length ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {members.map((member) => {
                    const label = member.display_name || member.email || member.user_id
                    const isSelf = member.user_id === currentUserId
                    return (
                      <div key={member.membership_id} className="relative group">
                        <ReducedProfileCard
                          type={member.role || 'Member'}
                          name={label}
                          tagline={member.tagline || member.email || member.user_id}
                          avatarUrl={resolveUserAvatarUrl(member.avatar_url) || null}
                        />
                        {canManage && !isSelf ? (
                          <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              disabled={busyUserId === member.user_id}
                              onClick={(event) => {
                                event.stopPropagation()
                                void removeMember(member)
                              }}
                            >
                              Remove
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="wf-user-settings__hint text-center p-8 border border-dashed border-border rounded-xl">
                  No members yet.
                </p>
              )}
            </SettingsPanelBody>
          </div>
        ) : null}

        {tab === 'delegation' ? (
          <AgentDelegationPanel
            workspaceId={workspaceId}
            currentUserId={currentUserId}
            members={members}
            loading={loading}
            onChanged={onChanged}
          />
        ) : null}

        {tab === 'invites' && canManage ? (
          <div className="space-y-4">
            <div className="flex items-center justify-end gap-3">
              <WfActionButton type="button" tone="primary" onClick={onInviteClick}>
                Invite member
              </WfActionButton>
            </div>

            <SettingsPanelBody error={error} status={status} bare>
              {pendingInvites.length ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {pendingInvites.map((invite) => (
                    <ReducedProfileCard
                      key={invite.id}
                      type="Pending"
                      name={invite.email}
                      tagline={invite.role || 'Member'}
                    />
                  ))}
                </div>
              ) : (
                <p className="wf-user-settings__hint text-center p-8 border border-dashed border-border rounded-xl">
                  No pending invites.
                </p>
              )}
            </SettingsPanelBody>
          </div>
        ) : null}

        {tab === 'updates' && canManage ? <StackUpdatesPanel onBadgeChange={setUpdatesBadge} /> : null}

        {tab === 'integrations' && canManage ? (
          <div className="space-y-4">
            <div className="flex items-center justify-end gap-3">
              <WfActionButton
                type="button"
                tone="primary"
                onClick={() => void saveIntegrations()}
                disabled={fieldsDisabled}
              >
                <Save className="w-4 h-4 mr-2" aria-hidden="true" />
                {saving ? 'Saving…' : 'Save all'}
              </WfActionButton>
            </div>

            <SettingsPanelBody error={error} status={status} className="space-y-8">
              <SettingsSection
                title="Email delivery"
                hint="SMTP for invites, sign-in codes, and notifications. Password is vault-encrypted on the stack."
              >
                <SmtpSettingsFields
                  disabled={fieldsDisabled}
                  onBindSave={(save) => {
                    smtpSaveRef.current = save
                  }}
                  onError={setError}
                />
              </SettingsSection>

              <SettingsSection
                title="Payments partner"
                hint="Stripe Connect OAuth — members connect their own Stripe accounts for billing and commerce tools."
              >
                <AdminStripeSetup
                  disabled={fieldsDisabled}
                  onBindSave={(save) => {
                    stripeSaveRef.current = save
                  }}
                />
              </SettingsSection>

              <SettingsSection
                title="Sign-in apps"
                hint="OAuth apps for member sign-in — Google, GitHub, Discord, and Telegram Login."
              >
                <AdminOAuthSetup
                  disabled={fieldsDisabled}
                  onBindSave={(save) => {
                    oauthSaveRef.current = save
                  }}
                />
              </SettingsSection>

              <SettingsSection
                title="Agent messaging"
                hint="Shared bot tokens and home channels for Discord and Telegram — separate from member sign-in OAuth."
              >
                <WorkspaceMessagingPanel
                  workspaceId={workspaceId}
                  disabled={fieldsDisabled}
                  onBindSave={(save) => {
                    messagingSaveRef.current = save
                  }}
                  onError={setError}
                />
              </SettingsSection>
            </SettingsPanelBody>
          </div>
        ) : null}
      </div>
    </SettingsSheetFrame>
  )
}
