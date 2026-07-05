import { useCallback, useEffect, useMemo, useState } from 'react'
import { Save } from 'lucide-react'

import { AvatarPickerGrid } from '@/components/onboarding/AvatarPickerGrid'
import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { AgentListItem } from '@/components/settings/AgentListItem'
import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { SettingsSection } from '@/components/settings/SettingsSection'
import { DialogField } from '@/components/dialogs/DialogField'
import { DialogSelect } from '@/components/dialogs/DialogSelect'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/dialogs/ConfirmDialog'
import { ReducedProfileCard } from '@/components/ui/ReducedProfileCard'
import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { useAgentRoute } from '@/contexts/AgentRouteContext'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useCrew } from '@/hooks/useCrew'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { resolveAgentAvatarUrl, resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { resolveLogoUrl } from '@/lib/avatarResolve'
import { agentAvatarPersistPayload, agentAvatarPickerValue, logoAvatarPersistPayload, logoAvatarPickerValue } from '@/lib/presetAssets'
import { findAgentByProfile } from '@/lib/hermesProfile'
import {
  fetchHermesProfileDetail,
  saveProfileSoul,
  updateHermesProfile,
  type HermesProfileDetailResponse,
} from '@/lib/hermesCatalogApi'
import { resolveAgentModelsProfile, resolveAgentTemplateProfile } from '@/lib/agentProfile'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { cn } from '@/lib/utils'
import { DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import {
  workframeAuthApi,
  type WorkspaceMember,
  type WorkspaceRoom,
  type WorkspaceRoomMember,
} from '@/lib/workframeAuthApi'

type ChatSettingsSheetProps = {
  open: boolean
  onClose: () => void
  initialAgentTab?: AgentSettingsTab
}

type ChatSettingsMode = 'agent' | 'project' | 'dm'
type AgentSettingsTab = 'identity' | 'instructions' | 'models'
type ProjectSettingsTab = 'details' | 'members' | 'agents'

function resolveChatMode(room: WorkspaceRoom | null): ChatSettingsMode {
  if (!room) return 'agent'
  if (room.agent_profile_id) return 'agent'
  if (room.room_type === 'direct') return 'dm'
  return 'project'
}

export function ChatSettingsSheet({ open, onClose, initialAgentTab }: ChatSettingsSheetProps) {
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { crew, reload: reloadCrew } = useCrew(projectName)
  const { activeRoom, setActiveRoom } = useWorkspacePanels()
  const { activeProfile, routes } = useAgentRoute()
  const { profile: sessionRuntimeProfile } = useHermesSession()
  const [me, setMe] = useState<{ user_id: string; workspace_id: string } | null>(null)
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [roomMembers, setRoomMembers] = useState<WorkspaceRoomMember[]>([])
  const [agentDetail, setAgentDetail] = useState<HermesProfileDetailResponse | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [tagline, setTagline] = useState('')
  const [role, setRole] = useState('')
  const [soul, setSoul] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [, setAvatarFileName] = useState('')
  const [agentTab, setAgentTab] = useState<AgentSettingsTab>('identity')
  const [projectRoomName, setProjectRoomName] = useState('')
  const [projectRoomTopic, setProjectRoomTopic] = useState('')
  const [projectRoomAvatarUrl, setProjectRoomAvatarUrl] = useState('')
  const [, setProjectRoomAvatarFileName] = useState('')
  const [projectTab, setProjectTab] = useState<ProjectSettingsTab>('details')
  const [addMemberUserId, setAddMemberUserId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<WorkspaceRoomMember | null>(null)
  const [busy, setBusy] = useState(false)

  const mode = useMemo(() => resolveChatMode(activeRoom), [activeRoom])
  const agentProfile = useMemo(
    () => resolveAgentTemplateProfile(activeRoom, activeProfile),
    [activeRoom, activeProfile],
  )
  const modelsProfile = useMemo(
    () => resolveAgentModelsProfile(activeRoom, activeProfile, sessionRuntimeProfile),
    [activeRoom, activeProfile, sessionRuntimeProfile],
  )
  const route = useMemo(
    () => routes.find((row) => row.profile === agentProfile) ?? null,
    [agentProfile, routes],
  )
  const crewMember = useMemo(
    () => findAgentByProfile(crew, agentProfile),
    [agentProfile, crew],
  )

  const dmPeer = useMemo((): WorkspaceMember | WorkspaceRoomMember | null => {
    if (mode !== 'dm' || !activeRoom || !me) return null
    const peerId = (activeRoom.member_user_ids ?? []).find((id) => id !== me.user_id)
    if (!peerId) {
      return roomMembers.find((member) => member.user_id && member.user_id !== me.user_id) ?? null
    }
    return (
      members.find((member) => member.user_id === peerId) ??
      roomMembers.find((member) => member.user_id === peerId) ??
      null
    )
  }, [activeRoom, me, members, mode, roomMembers])

  const dmPeerLabel = useMemo(() => {
    if (!dmPeer) return 'Direct message'
    return dmPeer.display_name || dmPeer.email || dmPeer.user_id || 'Contact'
  }, [dmPeer])

  const dmPeerEmail = useMemo(() => dmPeer?.email || '', [dmPeer])

  const canManageWorkspace = useMemo(
    () => members.some((member) => member.user_id === me?.user_id && ['owner', 'admin'].includes(member.role)),
    [me?.user_id, members],
  )

  const addableMembers = useMemo(() => {
    const inRoom = new Set(roomMembers.map((member) => member.user_id).filter(Boolean))
    return members.filter((member) => member.user_id && !inRoom.has(member.user_id))
  }, [members, roomMembers])

  const humanRoomMembers = useMemo(
    () => roomMembers.filter((member) => member.user_id),
    [roomMembers],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    setStatus('')
    try {
      const profile = await workframeAuthApi.getMe()
      const workspaceId =
        profile.current_workspace?.id ?? profile.default_workspace?.id ?? profile.workspaces?.[0]?.id ?? ''
      setMe({ user_id: profile.user.user_id, workspace_id: workspaceId })

      const memberPromise = workspaceId
        ? workframeAuthApi.listWorkspaceMembers(workspaceId)
        : Promise.resolve({ members: [] as WorkspaceMember[] })

      if (mode === 'agent') {
        const [memberList, detail] = await Promise.all([
          memberPromise,
          fetchHermesProfileDetail(agentProfile).catch(() => null),
        ])
        setMembers(memberList.members ?? [])
        setRoomMembers([])
        setAgentDetail(detail)
        if (detail?.ok) {
          setDisplayName(detail.display_name ?? '')
          setTagline(detail.tagline ?? '')
          setRole(detail.role ?? '')
          setSoul(detail.soul ?? '')
          const savedAvatar = detail.avatar_url || detail.avatar_id || ''
          setAvatarUrl(savedAvatar ? agentAvatarPickerValue(savedAvatar) : '')
          setAvatarFileName('')
          setAgentTab('identity')
        }
        return
      }

      if (!activeRoom?.id) {
        setMembers([])
        setRoomMembers([])
        setAgentDetail(null)
        return
      }

      const [memberList, roomMemberList] = await Promise.all([
        memberPromise,
        workframeAuthApi.listRoomMembers(activeRoom.id),
      ])
      setMembers(memberList.members ?? [])
      setRoomMembers(roomMemberList.members ?? [])
      setAgentDetail(null)
      setProjectRoomName(activeRoom.name ?? '')
      setProjectRoomTopic(activeRoom.topic ?? '')
      setProjectRoomAvatarUrl(logoAvatarPickerValue(activeRoom.avatar_url ?? ''))
      setProjectRoomAvatarFileName('')
      setProjectTab('details')
      setAddMemberUserId('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }, [activeRoom, agentProfile, mode])

  useEffect(() => {
    if (!open) return
    void load()
  }, [load, open])

  useEffect(() => {
    if (!open || !initialAgentTab) return
    setAgentTab(initialAgentTab)
  }, [open, initialAgentTab])

  const title = mode === 'agent' ? 'Agent settings' : mode === 'project' ? 'Project settings' : 'Conversation'

  const summary =
    mode === 'agent'
      ? route?.displayName || agentProfile
      : mode === 'project'
        ? activeRoom?.name || 'Group project'
        : dmPeerLabel

  const isNativeAgent = Boolean(crewMember?.is_native ?? agentDetail?.is_native)

  const saveAgentIdentity = async () => {
    setBusy(true)
    setError('')
    setStatus('')
    try {
      const avatar = avatarUrl ? agentAvatarPersistPayload(avatarUrl) : null
      if (isNativeAgent && me?.workspace_id) {
        await workframeAuthApi.patchNativeAgent({
          workspace_id: me.workspace_id,
          display_name: displayName,
          tagline,
          ...(avatar ? avatar : {}),
        })
      }
      await updateHermesProfile(agentProfile, {
        display_name: displayName,
        tagline,
        role,
        ...(avatar ?? {}),
      })
      setStatus('Agent identity saved.')
      reloadCrew()
      await load()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save agent identity'))
    } finally {
      setBusy(false)
    }
  }

  const saveAgentSoul = async () => {
    setBusy(true)
    setError('')
    setStatus('')
    try {
      if (isNativeAgent && me?.workspace_id) {
        await workframeAuthApi.patchNativeAgent({
          workspace_id: me.workspace_id,
          soul,
        })
      }
      await saveProfileSoul(agentProfile, soul)
      setStatus('Instructions saved.')
      await load()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save SOUL'))
    } finally {
      setBusy(false)
    }
  }

  const saveProjectDetails = async () => {
    if (!activeRoom?.id) return
    setBusy(true)
    setError('')
    setStatus('')
    try {
      const logo = projectRoomAvatarUrl ? logoAvatarPersistPayload(projectRoomAvatarUrl) : null
      const result = await workframeAuthApi.patchRoom(activeRoom.id, {
        name: projectRoomName,
        topic: projectRoomTopic,
        ...(logo ?? {}),
      })
      if (result.room) {
        setActiveRoom(result.room)
      }
      setStatus('Project details saved.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save project')
    } finally {
      setBusy(false)
    }
  }

  const addRoomMember = async () => {
    if (!activeRoom?.id || !addMemberUserId) return
    setBusy(true)
    setError('')
    setStatus('')
    try {
      await workframeAuthApi.addRoomMember(activeRoom.id, addMemberUserId)
      setAddMemberUserId('')
      setStatus('Member added.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add member')
    } finally {
      setBusy(false)
    }
  }

  const agentAvatarDisplayUrl = useMemo(() => {
    if (avatarUrl) return avatarUrl
    if (crewMember?.avatarUrl) return crewMember.avatarUrl
    if (route?.avatarUrl) return route.avatarUrl
    return (
      resolveAgentAvatarUrl({
        avatar_url: agentDetail?.avatar_url,
        avatar_id: agentDetail?.avatar_id,
        key: agentProfile,
        profile: agentProfile,
        is_native: isNativeAgent ? false : (crewMember?.is_native ?? agentDetail?.is_native),
      }) ?? ''
    )
  }, [
    agentDetail?.avatar_id,
    agentDetail?.avatar_url,
    agentDetail?.is_native,
    agentProfile,
    avatarUrl,
    crewMember,
    route?.avatarUrl,
  ])

  const agentFieldsDisabled = loading || busy || !canManageWorkspace
  const projectFieldsDisabled = loading || busy || !canManageWorkspace
  const canEditAgentModels = Boolean(me?.user_id && modelsProfile)

  const projectAvatarDisplayUrl = useMemo(() => {
    return resolveLogoUrl(projectRoomAvatarUrl || activeRoom?.avatar_url, DEFAULT_WORKSPACE_LOGO)
  }, [activeRoom?.avatar_url, projectRoomAvatarUrl])

  const removeRoomMember = async () => {
    if (!removeTarget?.user_id || !activeRoom?.id) return
    setBusy(true)
    setError('')
    try {
      await workframeAuthApi.removeRoomMember(activeRoom.id, removeTarget.user_id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove member')
    } finally {
      setBusy(false)
      setRemoveTarget(null)
    }
  }

  return (
    <>
      <SettingsSheetFrame
        open={open}
        onClose={onClose}
        title={
          mode === 'agent'
            ? 'Agent Settings'
            : mode === 'project'
              ? 'Project Settings'
              : title
        }
        summary={
          mode === 'agent'
            ? tagline || crewMember?.tagline || displayName || crewMember?.display_name || agentProfile || undefined
            : mode === 'project'
              ? projectRoomTopic || activeRoom?.topic || projectRoomName || activeRoom?.name || undefined
              : summary
        }
        titleId="wf-chat-settings-title"
        tabs={
          mode === 'agent'
            ? [
                { id: 'identity', label: 'Identity & Bio' },
                { id: 'instructions', label: 'Instructions' },
                { id: 'models', label: 'LLM Models' },
              ]
            : mode === 'project'
              ? [
                  { id: 'details', label: 'Project Details' },
                  { id: 'members', label: 'Project Members' },
                  { id: 'agents', label: 'Workspace Agents' },
                ]
              : undefined
        }
        activeTab={
          mode === 'agent' ? agentTab : mode === 'project' ? projectTab : undefined
        }
        onTabChange={
          mode === 'agent'
            ? (next) => setAgentTab(next as AgentSettingsTab)
            : mode === 'project'
              ? (next) => setProjectTab(next as ProjectSettingsTab)
              : undefined
        }
        loading={loading}
        contentFill={mode === 'agent' && agentTab === 'models'}
      >
        <div
          className={cn(
            'space-y-6',
            mode === 'agent' && agentTab === 'models' && 'wf-settings-fill-stack',
          )}
        >
          {mode === 'dm' && error ? <WorkframeNotice message={error} /> : null}
          {mode === 'dm' && status ? <WorkframeStatusNotice message={status} /> : null}

          {mode === 'agent' ? (
            agentTab === 'identity' ? (
              <div className="space-y-4" role="tabpanel">
                <div className="flex items-center justify-end gap-3">
                  <Button
                    type="button"
                    variant="default"
                    onClick={() => void saveAgentIdentity()}
                    disabled={agentFieldsDisabled}
                  >
                    <Save className="w-4 h-4 mr-2" aria-hidden="true" />
                    {busy ? 'Saving…' : 'Save changes'}
                  </Button>
                </div>

                {error ? <WorkframeNotice message={error} /> : null}
                {status ? <WorkframeStatusNotice message={status} /> : null}

                <div className="wf-wizard-panel wf-onboarding-form">
                  <OnboardingIdentityFields
                    avatarKind="agent"
                    avatarUrl={agentAvatarDisplayUrl}
                    onAvatarChange={(url) => {
                      setAvatarUrl(url)
                      setAvatarFileName('')
                    }}
                    disabled={agentFieldsDisabled}
                    primary={{
                      id: 'wf-agent-display-name',
                      label: 'Display name',
                      value: displayName,
                      onChange: setDisplayName,
                    }}
                    secondary={{
                      id: 'wf-agent-tagline',
                      label: 'Tagline',
                      value: tagline,
                      onChange: setTagline,
                    }}
                    body={{
                      id: 'wf-agent-role',
                      label: 'Role',
                      value: role,
                      onChange: setRole,
                      rows: 2,
                      placeholder: 'What this agent specializes in',
                    }}
                  />
                </div>
              </div>
            ) : agentTab === 'instructions' ? (
              <div className="space-y-4" role="tabpanel">
                <div className="flex items-center justify-end gap-3">
                  <Button
                    type="button"
                    variant="default"
                    onClick={() => void saveAgentSoul()}
                    disabled={agentFieldsDisabled}
                  >
                    <Save className="w-4 h-4 mr-2" aria-hidden="true" />
                    {busy ? 'Saving…' : 'Save instructions'}
                  </Button>
                </div>

                {error ? <WorkframeNotice message={error} /> : null}
                {status ? <WorkframeStatusNotice message={status} /> : null}

                <div className="wf-wizard-panel wf-onboarding-form">
                  <div className="wf-dialog-field">
                    <Label htmlFor="wf-agent-soul">Operating instructions</Label>
                    <p className="text-sm text-muted-foreground mb-2">
                      Layered on the system prompt — does not replace Workframe rules.
                    </p>
                    <Textarea
                      id="wf-agent-soul"
                      className="font-mono text-sm"
                      value={soul}
                      onChange={(event) => setSoul(event.target.value)}
                      disabled={agentFieldsDisabled}
                      rows={12}
                      placeholder="Personality and operating instructions"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4" role="tabpanel">
                {error ? <WorkframeNotice message={error} /> : null}
                {status ? <WorkframeStatusNotice message={status} /> : null}

                {canEditAgentModels ? (
                  <ModelPickerPanel
                    profile={modelsProfile}
                    workspaceId={me?.workspace_id}
                    embedded
                    onError={setError}
                    onChanged={() => void load()}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {loading ? 'Loading…' : 'Sign in to change models.'}
                  </p>
                )}
              </div>
            )
          ) : null}

          {mode === 'project' && activeRoom ? (
            projectTab === 'details' ? (
              <div className="space-y-4" role="tabpanel">
                <div className="flex items-center justify-end gap-3">
                  <Button
                    type="button"
                    variant="default"
                    onClick={() => void saveProjectDetails()}
                    disabled={projectFieldsDisabled}
                  >
                    <Save className="w-4 h-4 mr-2" aria-hidden="true" />
                    {busy ? 'Saving…' : 'Save project'}
                  </Button>
                </div>

                {error ? <WorkframeNotice message={error} /> : null}
                {status ? <WorkframeStatusNotice message={status} /> : null}

                <div className="wf-wizard-panel wf-onboarding-form">
                  <DialogField label="Logo">
                    <AvatarPickerGrid
                      kind="logo"
                      value={projectAvatarDisplayUrl}
                      onChange={(url) => {
                        setProjectRoomAvatarUrl(url)
                        setProjectRoomAvatarFileName('')
                      }}
                      disabled={projectFieldsDisabled}
                    />
                  </DialogField>

                  <DialogField label="Name" htmlFor="wf-project-name">
                    <Input
                      id="wf-project-name"
                      className="wf-dialog-input"
                      value={projectRoomName}
                      onChange={(event) => setProjectRoomName(event.target.value)}
                      disabled={projectFieldsDisabled}
                      placeholder="Project name"
                    />
                  </DialogField>

                  <DialogField label="Topic" htmlFor="wf-project-topic">
                    <Textarea
                      id="wf-project-topic"
                      value={projectRoomTopic}
                      onChange={(event) => setProjectRoomTopic(event.target.value)}
                      disabled={projectFieldsDisabled}
                      rows={2}
                      placeholder="What this project is for"
                    />
                  </DialogField>

                  {activeRoom?.slug ? (
                    <p className="text-xs font-mono text-muted-foreground">Slug: {activeRoom.slug}</p>
                  ) : null}
                </div>
              </div>
            ) : projectTab === 'members' ? (
              <div className="space-y-4" role="tabpanel">
                {error ? <WorkframeNotice message={error} /> : null}
                {status ? <WorkframeStatusNotice message={status} /> : null}

                {canManageWorkspace && addableMembers.length > 0 ? (
                  <div className="wf-wizard-panel wf-onboarding-form">
                    <div className="flex flex-col sm:flex-row gap-2 max-w-md">
                      <DialogSelect
                        id="wf-project-add-member"
                        className="flex-1"
                        value={addMemberUserId}
                        onValueChange={setAddMemberUserId}
                        placeholder="Workspace member"
                        disabled={busy}
                        options={addableMembers.map((member) => ({
                          value: member.user_id,
                          label: member.display_name || member.email || member.user_id,
                        }))}
                      />
                      <Button
                        type="button"
                        size="sm"
                        disabled={busy || !addMemberUserId}
                        onClick={() => void addRoomMember()}
                      >
                        Add
                      </Button>
                    </div>
                  </div>
                ) : null}

                {humanRoomMembers.length ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {humanRoomMembers.map((member) => {
                      const label = member.display_name || member.email || member.user_id || 'Member'
                      const isSelf = member.user_id === me?.user_id
                      return (
                        <div key={member.id} className="relative group">
                          <ReducedProfileCard
                            type={member.role || 'Member'}
                            name={label}
                            tagline={member.status || ''}
                            avatarUrl={resolveUserAvatarUrl(member.avatar_url) || null}
                          />
                          {!isSelf && member.user_id && canManageWorkspace ? (
                            <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                              <Button
                                type="button"
                                variant="destructive"
                                size="sm"
                                disabled={busy}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setRemoveTarget(member)
                                  setConfirmRemoveOpen(true)
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
                  <p className="text-sm text-muted-foreground text-center p-8 border border-dashed border-border rounded-xl">No human members in this project yet.</p>
                )}
              </div>
            ) : (
              <div className="space-y-4" role="tabpanel">
                {error ? <WorkframeNotice message={error} /> : null}

                {crew.length ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {crew.map((agent) => (
                      <AgentListItem
                        key={agent.profile}
                        name={agent.display_name || agent.profile}
                        tagline={agent.tagline || agent.role}
                        avatarUrl={agent.avatarUrl}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            )
          ) : null}

          {mode === 'dm' ? (
            <div className="space-y-6">
              <SettingsSection title="Contact">
                {dmPeer ? (
                  <ReducedProfileCard
                    name={dmPeerLabel}
                    tagline={dmPeerEmail || ''}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">Human direct message — no agent in this thread.</p>
                )}
              </SettingsSection>
              <p className="text-sm text-muted-foreground italic border-t border-border pt-4">
                Block and clear-history actions will land here in a later slice.
              </p>
            </div>
          ) : null}
        </div>
      </SettingsSheetFrame>

      <ConfirmDialog
        open={confirmRemoveOpen}
        onOpenChange={setConfirmRemoveOpen}
        title="Remove from project?"
        description="They will lose access to this project until re-added."
        confirmLabel="Remove"
        confirmVariant="warn"
        onConfirm={() => void removeRoomMember()}
      />
    </>
  )
}
