import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { PanelLeft, PanelLeftClose, Plus } from 'lucide-react'
import type { IDockviewPanelProps } from 'dockview'

import { PanelHeader } from '@/components/workspace/PanelHeader'
import { RailShortcutButtons } from '@/components/workspace/RailShortcutButtons'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useAgentRoute } from '@/contexts/AgentRouteContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { PANEL_IDS } from '@/lib/panelControlConfig'
import { PanelShell } from '@/components/workspace/PanelShell'
import { InviteMemberDialog } from '@/components/workspace/InviteMemberDialog'
import { CreateAgentDialog } from '@/components/workspace/CreateAgentDialog'
import { CreateProjectDialog } from '@/components/workspace/CreateProjectDialog'
import { WorkframeSettingsSheet } from '@/components/workspace/WorkframeSettingsSheet'
import { UserProfileSheet } from '@/components/workspace/UserProfileSheet'
import { RailItem } from '@/components/workspace/RailItem'
import { useCrew } from '@/hooks/useCrew'
import { cn } from '@/lib/utils'
import {
  workframeAuthApi,
  peekCachedSessionProfile,
  type SessionProfile,
  type WorkspaceMember,
  type WorkspaceRoom,
  watchWorkspaceEvents,
} from '@/lib/workframeAuthApi'
import {
  readActiveLaneHint,
  readCachedRooms,
  writeActiveLane,
  writeCachedRooms,
} from '@/lib/workspacePersist'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import { resolveLogoUrl, resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { isAgentChatRoom, resolveHermesProfileSlug } from '@/lib/agentProfile'
import { WORKFRAME_RAIL_LABEL } from '@/lib/panelDisplayLabels'
import { isProjectRoom } from '@/lib/roomChat'

const PROJECT_COLORS = ['#6c5ce7', '#00b894', '#0984e3', '#e17055', '#fdcb6e', '#a29bfe']

function routeStatusLabel(status: string | undefined): string | null {
  if (!status || status === 'online') return null
  if (status === 'unavailable') return 'Offline'
  if (status === 'not_installed') return 'Missing'
  return status
}

function isUserDirectRoom(room: WorkspaceRoom): boolean {
  return room.room_type === 'direct' && !room.agent_profile_id
}

function normalizeRoomSlug(seed: string): string {
  return seed
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
}

function dmPairKey(leftId: string, rightId: string): string {
  return [leftId, rightId].sort().join(':')
}

function projectColor(slug: string): string {
  let hash = 0
  for (const char of slug) hash = (hash + char.charCodeAt(0)) % PROJECT_COLORS.length
  return PROJECT_COLORS[hash] ?? PROJECT_COLORS[0]
}

export function AgentRailPanel({ api }: IDockviewPanelProps) {
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { crew, error, reload: reloadCrew } = useCrew(projectName)
  const { activeProfile, setActiveRoute } = useAgentRoute()
  const { activeRoom, closedPanelIds, openPanel, railExpanded, setRailExpanded, setActiveRoom, userSettingsOpen, userSettingsTab, openUserSettings, closeUserSettings, registerOpenAgentSettings, openChatSettings } = useWorkspacePanels()
  const [inviteOpen, setInviteOpen] = useState(false)
  const [createAgentOpen, setCreateAgentOpen] = useState(false)
  const [createProjectOpen, setCreateProjectOpen] = useState(false)
  const [me, setMe] = useState<SessionProfile | null>(() => peekCachedSessionProfile())
  const [workspaceMembers, setWorkspaceMembers] = useState<WorkspaceMember[]>([])
  const [workspaceRooms, setWorkspaceRooms] = useState<WorkspaceRoom[]>(() => {
    const cached = peekCachedSessionProfile()
    const ws = cached?.current_workspace ?? cached?.default_workspace ?? cached?.workspaces?.[0]
    return ws?.id ? readCachedRooms(ws.id) : []
  })
  const [workspaceError, setWorkspaceError] = useState('')
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const reloadTimerRef = useRef<number | null>(null)
  const laneBootstrapRef = useRef(false)

  const currentWorkspace = useMemo(
    () => me?.current_workspace ?? me?.default_workspace ?? me?.workspaces?.[0] ?? null,
    [me],
  )
  const currentUserId = me?.user?.user_id ?? ''
  const profileName = me?.user?.display_name || me?.user?.email || 'Profile'
  const profileEmail = me?.user?.email || 'Signed in'
  const canInvite = useMemo(
    () => workspaceMembers.some((member) => member.user_id === currentUserId && ['owner', 'admin'].includes(member.role)),
    [currentUserId, workspaceMembers],
  )

  const openChatPanel = useCallback(() => {
    openPanel(PANEL_IDS.chat)
  }, [openPanel])

  const reloadWorkspace = useCallback(async (): Promise<void> => {
    setWorkspaceLoading(true)
    setWorkspaceError('')
    try {
      const profile = await workframeAuthApi.getMe()
      setMe(profile)
      const nextWorkspace = profile.current_workspace ?? profile.default_workspace ?? profile.workspaces?.[0] ?? null
      const workspaceId = nextWorkspace?.id ?? ''
      if (!workspaceId) {
        setWorkspaceMembers([])
        setWorkspaceRooms([])
        return
      }
      const [members, rooms] = await Promise.all([
        workframeAuthApi.listWorkspaceMembers(workspaceId),
        workframeAuthApi.listWorkspaceRooms(workspaceId, true),
      ])
      const nextRooms = rooms.rooms ?? []
      setWorkspaceMembers(members.members ?? [])
      setWorkspaceRooms(nextRooms)
      writeCachedRooms(workspaceId, nextRooms)
    } catch (err) {
      setWorkspaceError(formatWorkframeErrorMessage(err, 'Load workspace'))
      if (!workspaceRooms.length) {
        setWorkspaceMembers([])
        setWorkspaceRooms([])
      }
    } finally {
      setWorkspaceLoading(false)
    }
  }, [workspaceRooms.length])

  const scheduleReload = useCallback(() => {
    if (reloadTimerRef.current) window.clearTimeout(reloadTimerRef.current)
    reloadTimerRef.current = window.setTimeout(() => {
      reloadTimerRef.current = null
      void reloadWorkspace()
      reloadCrew()
    }, 600)
  }, [reloadCrew, reloadWorkspace])

  useEffect(() => {
    void reloadWorkspace()
    return () => {
      if (reloadTimerRef.current) window.clearTimeout(reloadTimerRef.current)
    }
  }, [reloadWorkspace])

  useEffect(() => {
    if (!currentWorkspace?.id) return
    return watchWorkspaceEvents(currentWorkspace.id, scheduleReload)
  }, [currentWorkspace?.id, scheduleReload])

  const peerDirectRoomByUserId = useMemo(() => {
    const map = new Map<string, WorkspaceRoom>()
    for (const room of workspaceRooms) {
      if (!isUserDirectRoom(room)) continue
      const memberIds = (room.member_user_ids ?? []).filter(Boolean)
      if (!memberIds.includes(currentUserId)) continue
      const peerId = memberIds.find((id) => id !== currentUserId)
      if (peerId) map.set(peerId, room)
    }
    return map
  }, [currentUserId, workspaceRooms])

  const contacts = useMemo(
    () =>
      workspaceMembers
        .filter((member) => member.user_id && member.user_id !== currentUserId)
        .map((member) => ({
          member,
          room: peerDirectRoomByUserId.get(member.user_id) ?? null,
        })),
    [currentUserId, peerDirectRoomByUserId, workspaceMembers],
  )

  const projects = useMemo(() => {
    const list = workspaceRooms.filter(isProjectRoom)
    return [...list].sort((a, b) => {
      if (a.slug === 'general') return -1
      if (b.slug === 'general') return 1
      return a.name.localeCompare(b.name)
    })
  }, [workspaceRooms])

  const roomIsVisible = useCallback(
    (room: WorkspaceRoom | null | undefined) => {
      if (!room) return false
      if (isProjectRoom(room)) return true
      const memberIds = (room.member_user_ids ?? []).filter(Boolean)
      if (!memberIds.includes(currentUserId)) return false
      return isUserDirectRoom(room) || Boolean(room.agent_profile_id)
    },
    [currentUserId],
  )

  useEffect(() => {
    if (!activeRoom || !workspaceRooms.length) return
    const refreshed = workspaceRooms.find((room) => room.id === activeRoom.id)
    if (!refreshed) {
      if (workspaceLoading) return
      setActiveRoom(null)
      return
    }
    if (!roomIsVisible(refreshed)) {
      if (workspaceLoading) return
      setActiveRoom(null)
      return
    }
    if (refreshed !== activeRoom) setActiveRoom(refreshed)
  }, [activeRoom, roomIsVisible, setActiveRoom, workspaceLoading, workspaceRooms])

  const selectRoom = useCallback(
    (room: WorkspaceRoom) => {
      const fresh = workspaceRooms.find((r) => r.id === room.id) ?? room
      const prof = resolveHermesProfileSlug(fresh, activeProfile)
      if (prof) setActiveRoute(prof)
      setActiveRoom(fresh)
      if (currentWorkspace?.id && currentUserId) {
        writeActiveLane({
          workspaceId: currentWorkspace.id,
          userId: currentUserId,
          roomId: fresh.id,
          room: fresh,
        })
      }
      openChatPanel()
    },
    [activeProfile, currentUserId, currentWorkspace?.id, openChatPanel, setActiveRoom, setActiveRoute, workspaceRooms],
  )

  const selectAgent = useCallback(
    async (profile: string, memberName: string) => {
      const existing = workspaceRooms.find(
        (room) =>
          room.room_type === 'direct' &&
          isAgentChatRoom(room) &&
          resolveHermesProfileSlug(room, profile) === profile &&
          (room.member_user_ids ?? []).includes(currentUserId),
      )
      if (existing) {
        selectRoom(existing)
        return
      }
      if (!currentWorkspace || !currentUserId) {
        setActiveRoom(null)
        setActiveRoute(profile)
        openChatPanel()
        return
      }
      try {
        const created = await workframeAuthApi.createWorkspaceRoom(currentWorkspace.id, {
          name: memberName,
          slug: normalizeRoomSlug(`dm-${currentUserId}-${profile}`),
          room_type: 'direct',
          agent_profile_id: profile,
          member_user_ids: [currentUserId],
        })
        setWorkspaceRooms((current) => [created.room, ...current.filter((room) => room.id !== created.room.id)])
        selectRoom(created.room)
      } catch {
        setActiveRoom(null)
        setActiveRoute(profile)
        openChatPanel()
      }
    },
    [currentUserId, currentWorkspace, openChatPanel, selectRoom, setActiveRoom, setActiveRoute, workspaceRooms],
  )

  useEffect(() => {
    registerOpenAgentSettings(async (profile, displayName) => {
      await selectAgent(profile, displayName)
      openChatSettings()
    })
    return () => registerOpenAgentSettings(null)
  }, [openChatSettings, registerOpenAgentSettings, selectAgent])

  const bootstrapDefaultProject = useCallback(() => {
    const general = workspaceRooms.find((room) => room.slug === 'general')
    if (general) {
      selectRoom(general)
      return
    }
    const firstProject = workspaceRooms.find((room) => isProjectRoom(room))
    if (firstProject) {
      selectRoom(firstProject)
    }
  }, [selectRoom, workspaceRooms])

  const workspaceTagline = currentWorkspace?.tagline?.trim() || ''

  useEffect(() => {
    if (activeRoom || laneBootstrapRef.current) return
    if (!currentWorkspace?.id || !currentUserId || workspaceLoading) return

    const hint = readActiveLaneHint(currentWorkspace.id, currentUserId)
    const hintedRoomId = hint?.roomId?.trim() || ''

    if (hintedRoomId && workspaceRooms.length) {
      const restored =
        workspaceRooms.find((room) => room.id === hintedRoomId) ??
        (hint?.room?.id === hintedRoomId ? hint.room : null)
      if (restored && roomIsVisible(restored)) {
        laneBootstrapRef.current = true
        selectRoom(restored)
        return
      }
    }

    if (!workspaceRooms.length) return
    laneBootstrapRef.current = true
    bootstrapDefaultProject()
  }, [
    activeRoom,
    bootstrapDefaultProject,
    currentUserId,
    currentWorkspace?.id,
    roomIsVisible,
    selectRoom,
    workspaceLoading,
    workspaceRooms,
  ])

  const openDirectMessage = useCallback(
    async (member: WorkspaceMember) => {
      const contactUserId = member.user_id?.trim() || ''
      const contactName = member.display_name || member.email || 'Contact'
      if (!currentWorkspace || !currentUserId || !contactUserId) {
        setActiveRoom(null)
        openChatPanel()
        return
      }

      const existing = peerDirectRoomByUserId.get(contactUserId)
      if (existing) {
        selectRoom(existing)
        return
      }

      try {
        const created = await workframeAuthApi.createWorkspaceRoom(currentWorkspace.id, {
          name: contactName,
          slug: normalizeRoomSlug(`dm-${dmPairKey(currentUserId, contactUserId)}`),
          room_type: 'direct',
          member_user_ids: [currentUserId, contactUserId],
        })
        setWorkspaceRooms((current) => [created.room, ...current.filter((room) => room.id !== created.room.id)])
        selectRoom(created.room)
      } catch {
        setActiveRoom(null)
        openChatPanel()
      }
    },
    [currentUserId, currentWorkspace, openChatPanel, peerDirectRoomByUserId, selectRoom, setActiveRoom],
  )

  const toggleExpanded = useCallback(() => {
    setRailExpanded(!railExpanded)
  }, [railExpanded, setRailExpanded])

  const railToggle = (
    <button
      type="button"
      className="wf-agent-rail__toggle"
      onClick={toggleExpanded}
      aria-label={railExpanded ? 'Collapse workframe rail' : 'Expand workframe rail'}
      aria-expanded={railExpanded}
    >
      {railExpanded ? <PanelLeftClose aria-hidden="true" /> : <PanelLeft aria-hidden="true" />}
    </button>
  )

  return (
    <>
      <PanelShell className={cn('wf-panel--rail', railExpanded ? 'wf-panel--rail-expanded' : 'wf-panel--rail-collapsed')}>
        {railExpanded ? (
          <PanelHeader
            label={WORKFRAME_RAIL_LABEL}
            panelId={PANEL_IDS.crew}
            api={api}
            trailing={railToggle}
            renderSettings={({ open, onClose }) => (
              <WorkframeSettingsSheet
                open={open}
                onClose={onClose}
                workspaceId={currentWorkspace?.id ?? ''}
                workspaceSlug={currentWorkspace?.slug}
                currentUserId={currentUserId}
                canManage={canInvite}
                onInviteClick={() => {
                  onClose()
                  setInviteOpen(true)
                }}
                onChanged={scheduleReload}
              />
            )}
          />
        ) : (
          <div className="wf-panel__header">{railToggle}</div>
        )}

        <ScrollArea axis="vertical" className="wf-agent-rail-scroll">
          <nav className={cn('wf-agent-rail', !railExpanded && 'wf-agent-rail--collapsed')} aria-label="Workspace rail">
            {error && railExpanded ? <WorkframeNotice message={error} /> : null}

            <RailSection
              title="Projects"
              expanded={railExpanded}
              count={projects.length}
              emptyLabel={workspaceLoading ? 'Loading projects…' : 'No projects yet'}
              addLabel="Create project"
              onAdd={() => setCreateProjectOpen(true)}
            >
              {projects.map((room) => (
                <RailItem
                  key={room.id}
                  expanded={railExpanded}
                  active={activeRoom?.id === room.id}
                  ariaLabel={`Open project ${room.name}`}
                    primary={room.name}
                    secondary={room.topic?.trim() || (room.slug === 'general' ? workspaceTagline : '')}
                  avatarName={room.name}
                  avatarSrc={resolveLogoUrl(room.avatar_url, DEFAULT_WORKSPACE_LOGO)}
                  avatarColor={projectColor(room.slug)}
                  onClick={() => selectRoom(room)}
                />
              ))}
            </RailSection>

            <RailSection
              title="Contacts"
              expanded={railExpanded}
              count={contacts.length}
              emptyLabel={workspaceLoading ? 'Loading contacts…' : 'No contacts yet'}
              addLabel="Add contact"
              onAdd={canInvite ? () => setInviteOpen(true) : undefined}
            >
              {contacts.map(({ member, room }) => {
                const label = member.display_name || member.email || 'Contact'
                const isActive = room ? activeRoom?.id === room.id : false
                return (
                  <RailItem
                    key={member.membership_id}
                    expanded={railExpanded}
                    active={isActive}
                    ariaLabel={`Open direct message with ${label}`}
                    primary={label}
                    secondary={member.tagline || member.email || 'Workspace member'}
                    avatarSrc={resolveUserAvatarUrl(member.avatar_url)}
                    avatarName={label}
                    onClick={() => void openDirectMessage(member)}
                  />
                )
              })}
            </RailSection>

            <RailSection
              title="Agents"
              expanded={railExpanded}
              count={crew.length}
              emptyLabel="No agents available"
              addLabel="Create agent"
              onAdd={() => setCreateAgentOpen(true)}
            >
              {crew.map((member) => {
                const isActive = Boolean(
                  activeRoom &&
                  isAgentChatRoom(activeRoom) &&
                  resolveHermesProfileSlug(activeRoom, member.profile) === member.profile,
                )
                const statusLabel = routeStatusLabel(member.route_status)
                const tagline = member.tagline || member.role
                const secondary = statusLabel ? `${tagline} · ${statusLabel}` : tagline
                return (
                  <RailItem
                    key={member.key}
                    expanded={railExpanded}
                    active={isActive}
                    ariaLabel={member.display_name}
                    primary={member.display_name}
                    secondary={secondary}
                    avatarSrc={member.avatarUrl}
                    avatarName={member.display_name}
                    avatarInitials={member.code}
                    avatarColor={member.color}
                    onClick={() => void selectAgent(member.profile, member.display_name)}
                  />
                )
              })}
            </RailSection>

            {workspaceError && railExpanded ? (
              <WorkframeNotice message={workspaceError} />
            ) : null}

            <RailShortcutButtons projectName={projectName} closedPanelIds={closedPanelIds} expanded={railExpanded} onOpen={openPanel} />
          </nav>
        </ScrollArea>

        <div className="wf-agent-rail__bottom">
          <RailItem
            expanded={railExpanded}
            active={userSettingsOpen}
            ariaLabel="Open user profile and settings"
            primary={profileName}
            secondary={profileEmail}
            avatarSrc={resolveUserAvatarUrl(me?.user?.avatar_url)}
            avatarName={profileName}
            onClick={() => openUserSettings('profile')}
          />
        </div>

        <UserProfileSheet
          open={userSettingsOpen}
          onOpenChange={(next) => (next ? openUserSettings(userSettingsTab) : closeUserSettings())}
          initialTab={userSettingsTab}
        />
      </PanelShell>

      <InviteMemberDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        workspaceId={currentWorkspace?.id ?? ''}
        workspaceName={currentWorkspace?.display_name ?? 'Workspace'}
        onInvited={scheduleReload}
      />
      <CreateAgentDialog
        open={createAgentOpen}
        onOpenChange={setCreateAgentOpen}
        onCreated={(result) => {
          reloadCrew()
          scheduleReload()
          if (result.room) {
            selectRoom(result.room)
          } else if (result.room_id) {
            const existing = workspaceRooms.find((room) => room.id === result.room_id)
            if (existing) selectRoom(existing)
          } else if (result.profile) {
            void selectAgent(
              result.profile,
              crew.find((row) => row.profile === result.profile)?.display_name ?? result.profile,
            )
          }
        }}
      />
      <CreateProjectDialog
        open={createProjectOpen}
        onOpenChange={setCreateProjectOpen}
        workspaceId={currentWorkspace?.id ?? ''}
        onCreated={scheduleReload}
      />
    </>
  )
}

type RailSectionProps = {
  title: string
  expanded: boolean
  count: number
  emptyLabel: string
  addLabel?: string
  onAdd?: () => void
  children: ReactNode
}

function RailSection({ title, expanded, count, emptyLabel, addLabel, onAdd, children }: RailSectionProps) {
  return (
    <section className="wf-agent-rail__section" aria-label={title}>
      {expanded ? (
        <div className="wf-agent-rail__section-header">
          <h3 className="wf-agent-rail__section-title">{title}</h3>
          {onAdd ? (
            <button
              type="button"
              className="wf-agent-rail__section-action wf-agent-rail__section-action--icon"
              onClick={onAdd}
              aria-label={addLabel ?? `Add to ${title}`}
            >
              <Plus aria-hidden="true" size={16} />
            </button>
          ) : (
            <span className="wf-agent-rail__section-count">{count}</span>
          )}
        </div>
      ) : null}
      {count > 0 ? children : expanded ? <p className="wf-agent-rail__empty">{emptyLabel}</p> : null}
    </section>
  )
}
