import {
  clearStoredSessionTokens,
  setStoredSessionTokens,
  workframeAuthHeaders,
} from '@/lib/workframeSession'
import { authenticatedFetch } from '@/lib/authenticatedFetch'
import { noticeMessage, parseApiErrorResponse } from '@/lib/workframeErrors'

export { setStoredSessionId, setStoredSessionTokens } from '@/lib/workframeSession'

export type SetupStatus = {
  setup_complete: boolean
}

export type InstallStatus = {
  ok: boolean
  phase: string
  hermes_present: boolean
  setup_complete: boolean
  api_ok: boolean
  deployment_mode: string
  mode: string
  smtp_configured: boolean
  install_complete: boolean
  install_window_open: boolean
  native_profile: string
}

export type PublishHints = {
  ok: boolean
  hostname: string
  apex_domain: string
  public_ipv4: string | null
  ui_port: number
  health_url: string
  dns: { type: string; name: string; value: string; ttl: string }
  registrar_links: Array<{ label: string; url: string }>
  setup_command: string
  project_root: string
  dns_cname?: {
    type: string
    name: string
    value: string
    hint: string
  } | null
}

export type StackConfig = {
  deployment_mode: string
  app_base_url: string
  install_complete: boolean
  smtp: {
    provider: string
    host: string
    port: number
    user: string
    from: string
    admin_email?: string
    secure: string
    configured: boolean
    tested?: boolean
    setup_complete?: boolean
    admin_verified?: boolean
    has_password: boolean
  }
  wizard?: {
    admin_verified: boolean
    resume_step: string
    owner_claimed: boolean
  }
  google_oauth: {
    client_id: string
    has_secret: boolean
    enabled: boolean
  }
  github_oauth: {
    client_id: string
    has_secret: boolean
    enabled: boolean
  }
  discord_oauth: {
    client_id: string
    has_secret: boolean
    enabled: boolean
  }
  telegram_login: {
    bot_username: string
    has_token: boolean
    enabled: boolean
    domain?: string
  }
  stripe_connect: {
    client_id: string
    has_secret: boolean
    enabled: boolean
  }
  site_branding: {
    title: string
    description: string
    theme_color: string
    has_og_image: boolean
    has_favicon: boolean
  }
}

export type AuthStartResponse = {
  status: string
  otp_code?: string
  email_sent?: boolean
  email_error?: string
  _dev_warning?: string
}

export type SessionUser = {
  user_id: string
  display_name: string | null
  avatar_url: string | null
  email?: string | null
  tagline?: string | null
  bio?: string | null
  platform_ids?: Record<string, string>
}

export type SessionWorkspace = {
  id: string
  slug: string
  display_name: string
  description?: string | null
  tagline?: string | null
  avatar_url?: string | null
}

export type WorkspaceDetail = SessionWorkspace & {
  tagline?: string | null
  status?: string
  owner_id?: string
  created_at?: string
  updated_at?: string
  integrations?: {
    github_oauth_configured?: boolean
    github_oauth_client_id?: string
    github_oauth_has_secret?: boolean
    messaging?: {
      discord?: {
        bot_token_configured?: boolean
        home_channel?: string
        allowed_users?: string
      }
      telegram?: {
        bot_token_configured?: boolean
        home_channel?: string
        allowed_users?: string
      }
    }
  }
  credential_mode?: 'byok' | 'workspace'
  admin_onboarding_done?: boolean
}

export type StackProductUpdateStatus = {
  current?: string
  latest?: string
  agent_version?: string
  image_tag?: string
  update_available: boolean
  can_update: boolean
  state: 'current' | 'available' | 'blocked' | 'unsupported' | 'error'
  reason?: string | null
  update_mode?: string
  install_kind?: string
  components?: string[]
  current_image?: string
  current_digest?: string
  latest_digest?: string
  image?: string
  can_restart_gateway?: boolean
  download_url?: string
}

export type StackUpdatesStatus = {
  ok: boolean
  docker_available: boolean
  docker_sock_on_api?: boolean
  supervisor_configured?: boolean
  update_apply_ready?: boolean
  update_apply_channel?: 'api_docker' | 'supervisor' | null
  compose_dir?: string
  project_root?: string
  workframe: StackProductUpdateStatus & {
    current: string
    latest: string
    components: string[]
  }
  hermes: StackProductUpdateStatus & {
    current: string
    agent_version?: string
    image_tag?: string
    latest: string
    current_image: string
    current_digest: string
    latest_digest: string
    image: string
  }
  desktop: StackProductUpdateStatus & {
    current: string
    latest: string
    download_url: string
  }
}

export type WorkframeApiHealth = {
  ok: boolean
  version: string
  mode: string
  secure_mode: boolean
  deployment_mode: string
  admin_updates_enabled: boolean
  docker_sock_on_api: boolean
  proxy_token_configured: boolean
  vault_sealed: boolean
  vault_envelope: boolean
}

export type OnboardingState = {
  ok: boolean
  complete: boolean
  step: 'workspace' | 'admin_integrations' | 'admin' | 'workspace_provider' | 'user_provider' | 'done'
  credential_mode: 'byok' | 'workspace'
  workspace_id?: string
  role?: string
  has_llm_provider?: boolean
}

export type SessionProfile = {
  ok: boolean
  user: SessionUser
  workspaces?: SessionWorkspace[]
  current_workspace?: SessionWorkspace | null
  default_workspace?: SessionWorkspace | null
  hermes_dashboard_access?: boolean
}

export type UserCredential = {
  credential_id: string
  credential_ref: string
  provider: string
  credential_type: string
  label: string
  is_active: number | boolean
  created_at?: string
  updated_at?: string
  workspace_id?: string | null
  agent_profile_id?: string | null
  user_id?: string | null
}

export type UserCredentialList = {
  ok: boolean
  credentials: UserCredential[]
}

export type SavedUserCredential = UserCredential & {
  profile_home: string
  env_path: string
  auth_path: string
}

export type ProviderConnectMode = 'api_key' | 'bot_token' | 'oauth'

export type ProviderConnectRow = {
  id: string
  label: string
  category: string
  connect_mode: ProviderConnectMode
  env_var?: string
  extra_env_vars?: string[]
  description: string
  connected: boolean
  source?: string | null
  stack_available?: boolean
  credential_id?: string | null
  credential_ref?: string | null
  profile_home?: string
  hermes_auth_id?: string
  oauth_configured?: boolean | null
  user_only?: boolean
}

export type ProviderConnectList = {
  ok: boolean
  providers: ProviderConnectRow[]
  profile_home?: string
  stack_managed?: boolean
}

export type OAuthStartResponse = {
  ok: boolean
  provider?: string
  hermes_auth_id?: string
  flow?: 'device_code' | 'redirect'
  session_id?: string
  status?: 'pending' | 'connected' | 'error'
  verification_uri?: string | null
  user_code?: string | null
  output?: string
  redirect_url?: string | null
  error?: string | null
  message?: string | null
}

export type OAuthStatusResponse = {
  ok: boolean
  provider?: string
  session_id?: string
  status?: 'pending' | 'connected' | 'error'
  verification_uri?: string | null
  user_code?: string | null
  error?: string | null
  message?: string | null
}

export type WorkspaceMember = {
  membership_id: string
  workspace_id: string
  user_id: string
  email?: string | null
  display_name?: string | null
  tagline?: string | null
  avatar_url?: string | null
  role: string
  status: string
  invited_by?: string | null
  created_at?: string
  updated_at?: string
}

export type WorkspaceInvite = {
  id: string
  workspace_id: string
  email: string
  role: string
  invited_by_user_id?: string | null
  invited_by_email?: string | null
  expires_at: string
  created_at: string
  accepted_at?: string | null
  accepted_by_user_id?: string | null
  deleted_at?: string | null
}

export type WorkspaceRoom = {
  id: string
  workspace_id: string
  agent_profile_id?: string | null
  /** Hermes profile directory slug (use for chat/settings APIs). */
  hermes_profile?: string | null
  name: string
  slug: string
  topic?: string | null
  avatar_url?: string | null
  room_type: 'lane' | 'group' | 'direct' | 'channel' | string
  status: string
  created_by?: string | null
  created_at?: string
  updated_at?: string
  member_user_ids?: string[]
}

export type WorkspaceRoomsList = {
  ok: boolean
  workspace_id: string
  rooms: WorkspaceRoom[]
}

export type WorkspaceRoomMember = {
  id: string
  room_id: string
  user_id?: string | null
  agent_profile_id?: string | null
  display_name?: string | null
  email?: string | null
  handle?: string | null
  mention_handle?: string | null
  hermes_profile?: string | null
  avatar_url?: string | null
  avatar_id?: string | null
  role: string
  status: string
  joined_at?: string
  updated_at?: string
  deleted_at?: string | null
}

export type WorkspaceRoomMembersList = {
  ok: boolean
  room_id: string
  members: WorkspaceRoomMember[]
}

export type WorkspaceRoomMessage = {
  id: string
  room_id: string
  sender_user_id?: string | null
  sender_agent_id?: string | null
  sender_agent_slug?: string | null
  sender_agent_name?: string | null
  parent_message_id?: string | null
  content: string
  content_type: string
  metadata?: string | null
  is_edited?: number | boolean
  created_at?: string
  updated_at?: string
  deleted_at?: string | null
}

export type WorkspaceRoomMessagesList = {
  ok: boolean
  messages: WorkspaceRoomMessage[]
  total?: number
  limit?: number
  offset?: number
}

export type RoomSessionRow = {
  id: string
  room_id: string
  agent_profile_id: string
  agent_slug: string
  hermes_profile: string
  session_id: string
  title: string
  status: string
  message_count: number
  created_at: string
  updated_at: string
  active: boolean
}

export type RoomSessionsList = {
  ok: boolean
  room_id: string
  sessions: RoomSessionRow[]
}

export type RoomSessionActivateResponse = {
  ok: boolean
  profile: string
  template_profile?: string
  agent_display_name?: string
  room_id: string
  session_id: string
  title?: string
  resumed?: boolean
  llm_ready?: boolean
  has_llm_provider?: boolean
}

export type WorkspaceEventFrame = {
  type: string
  workspace_id: string
  revision?: string
  files_revision?: string
  ts?: number
}

let cachedSessionProfile: SessionProfile | null = null

/** Last successful `/me` — instant boot before network round-trip. */
export function peekCachedSessionProfile(): SessionProfile | null {
  return cachedSessionProfile
}

function rememberSessionProfile(profile: SessionProfile): SessionProfile {
  cachedSessionProfile = profile
  return profile
}

export type DelegationGrant = {
  id: string
  workspace_id: string
  grantor_user_id: string
  grantee_user_id: string
  scope: string
  expires_at?: string | null
  created_at: string
  updated_at: string
}

export type CohortAgent = {
  role: string
  display_name: string
  runtime_slug: string
  alias: string
  template_slug: string
  tagline?: string
  avatar_url?: string | null
  avatar_id?: string | null
}

export type WorkspaceMembersList = {
  ok: boolean
  workspace_id: string
  members: WorkspaceMember[]
}

export type WorkspaceInvitesList = {
  ok: boolean
  workspace_id: string
  invites: WorkspaceInvite[]
}

async function request<T>(path: string, options: RequestInit = {}, retryOn401 = true): Promise<T> {
  const headers = workframeAuthHeaders(options.headers)

  if (!(options.body instanceof FormData) && !headers.has('content-type')) {
    headers.set('content-type', 'application/json')
  }

  const response = await authenticatedFetch(
    `/api${path}`,
    {
      ...options,
      headers,
    },
    retryOn401,
  )

  if (!response.ok) {
    const info = await parseApiErrorResponse(response)
    throw new Error(noticeMessage(info))
  }

  const text = await response.text()
  return (text ? JSON.parse(text) : null) as T
}

export function watchWorkspaceEvents(
  workspaceId: string,
  onEvent: (frame: WorkspaceEventFrame) => void,
): () => void {
  const source = new EventSource(`/api/workspace/${encodeURIComponent(workspaceId)}/events`)
  source.onmessage = (event) => {
    try {
      const frame = JSON.parse(event.data) as WorkspaceEventFrame
      if (frame.type === 'heartbeat') return
      onEvent(frame)
    } catch {
      // Ignore malformed events; the stream is only a refresh trigger.
    }
  }
  source.onerror = () => {
    // EventSource auto-reconnects. Keep the handler quiet.
  }
  return () => source.close()
}

export const workframeAuthApi = {
  getSetupStatus() {
    return request<SetupStatus>('/setup/status')
  },

  completeSetup(data: {
    workframe_name: string
    agent_name: string
    workframe_description?: string
    agent_personality?: string
  }) {
    return request<{ ok: boolean; workspace_id: string; agent_id: string; room_id?: string; hermes?: unknown }>('/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  startEmailVerification(email: string) {
    return request<AuthStartResponse>('/auth/start', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }, false)
  },

  verifyEmailCode(email: string, code: string) {
    return request<
      SessionProfile & {
        user_id?: string
        is_new_user?: boolean
        session_id?: string
        refresh_token?: string
      }
    >('/auth/verify', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    }, false).then((data) => {
      if (data.session_id) {
        setStoredSessionTokens(data.session_id, data.refresh_token)
      }
      return data
    })
  },

  async restoreSession() {
    try {
      return rememberSessionProfile(await request<SessionProfile>('/me'))
    } catch {
      try {
        const refreshed = await request<{
          ok: boolean
          session_id: string
        }>('/auth/refresh', {
          method: 'POST',
          credentials: 'include',
          body: JSON.stringify({}),
        }, false)
        setStoredSessionTokens(refreshed.session_id)
        return rememberSessionProfile(await request<SessionProfile>('/me'))
      } catch {
        clearStoredSessionTokens()
        cachedSessionProfile = null
        throw new Error('no_session')
      }
    }
  },

  /** Session probe without refresh retry or session-expired side effects (install window). */
  async peekSession(): Promise<SessionProfile | null> {
    try {
      return rememberSessionProfile(await request<SessionProfile>('/me', {}, false))
    } catch {
      return null
    }
  },

  async peekOnboarding(): Promise<OnboardingState | null> {
    try {
      return await request<OnboardingState>('/me/onboarding', {}, false)
    } catch {
      return null
    }
  },

  getMeta() {
    return request<{ ok: boolean; app_base_url?: string }>('/meta')
  },

  getMe() {
    return request<SessionProfile>('/me').then(rememberSessionProfile)
  },

  getOnboarding() {
    return request<OnboardingState>('/me/onboarding')
  },

  listRoomMessages(roomId: string, limit = 100, offset = 0) {
    return request<WorkspaceRoomMessagesList>(`/rooms/${roomId}/messages?limit=${encodeURIComponent(String(limit))}&offset=${encodeURIComponent(String(offset))}`)
  },

  listRoomActivity(roomId: string) {
    return request<{ ok: boolean; room_id: string; activity: Array<Record<string, unknown>> }>(`/rooms/${roomId}/activity`)
  },

  listRoomSessions(roomId: string) {
    return request<RoomSessionsList>(`/rooms/${roomId}/sessions`)
  },

  activateRoomSession(
    roomId: string,
    data: {
      session_id: string
      profile?: string
      source_id?: string
      client_id?: string
      binding_version?: number
    },
  ) {
    return request<RoomSessionActivateResponse>(`/rooms/${roomId}/sessions/activate`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  sendRoomMessage(roomId: string, data: { content: string; content_type?: string; parent_message_id?: string | null; sender_user_id?: string; sender_agent_id?: string; invoke_agents?: boolean }) {
    return request<{ ok: boolean; message_id: string; agent_mentions?: string[]; user_mentions?: string[] }>(`/rooms/${roomId}/messages/send`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  updateMe(data: {
    display_name?: string
    avatar_url?: string
    tagline?: string
    bio?: string
    platform_ids?: Record<string, string>
  }) {
    return request<SessionProfile>('/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  linkTelegram(data: Record<string, string | number>) {
    return request<{ ok: boolean; provider?: string; platform_ids?: Record<string, string>; error?: string }>(
      '/me/telegram/link',
      { method: 'POST', body: JSON.stringify(data) },
    )
  },

  listUserCredentials() {
    return request<UserCredentialList>('/me/credentials')
  },

  saveUserCredential(data: {
    provider: string
    credential_type: 'api_key' | 'oauth' | 'bot_token'
    secret: string
    env_var?: string
    label?: string
  }) {
    return request<SavedUserCredential>('/me/credentials', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  storeWorkspaceCredential(
    workspaceId: string,
    data: { provider: string; api_key: string; label?: string },
  ) {
    return request<{ ok: boolean; credential_id?: string; error?: string }>(
      `/workspace/${encodeURIComponent(workspaceId)}/credentials/store`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    )
  },

  listProviders(workspaceId?: string) {
    const query = workspaceId?.trim() ? `?workspace_id=${encodeURIComponent(workspaceId.trim())}` : ''
    return request<ProviderConnectList>(`/me/providers${query}`)
  },

  disconnectCredential(credentialId: string) {
    return request<{ ok: boolean; credential_id?: string; error?: string }>(`/me/credentials/${credentialId}`, {
      method: 'DELETE',
    })
  },

  disconnectProvider(providerId: string) {
    return request<{ ok: boolean; provider?: string; error?: string }>(`/me/providers/${providerId}/disconnect`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },

  startProviderOAuth(providerId: string, workspaceId?: string) {
    return request<OAuthStartResponse>(`/me/oauth/${providerId}/start`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId ?? '' }),
    })
  },

  providerOAuthStatus(providerId: string, sessionId: string) {
    const query = `?session_id=${encodeURIComponent(sessionId)}`
    return request<OAuthStatusResponse>(`/me/oauth/${providerId}/status${query}`)
  },

  listWorkspaceMembers(workspaceId: string) {
    return request<WorkspaceMembersList>(`/workspace/${workspaceId}/members`)
  },

  getWorkspace(workspaceId: string) {
    return request<{ ok: boolean; workspace: WorkspaceDetail }>(`/workspace/${workspaceId}`)
  },

  patchWorkspace(
    workspaceId: string,
    data: { display_name?: string; description?: string; avatar_url?: string; tagline?: string },
  ) {
    return request<{ ok: boolean; workspace: WorkspaceDetail }>(`/workspace/${workspaceId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  patchWorkspaceIntegrations(
    workspaceId: string,
    data: {
      github_oauth_client_id?: string
      github_oauth_client_secret?: string
      credential_mode?: 'byok' | 'workspace'
      admin_onboarding_done?: boolean
      admin_integrations_done?: boolean
      messaging?: {
        discord?: { home_channel?: string; allowed_users?: string }
        telegram?: { home_channel?: string; allowed_users?: string }
      }
    },
  ) {
    return request<{ ok: boolean; workspace: WorkspaceDetail }>(`/workspace/${workspaceId}/integrations`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  listWorkspaceInvites(workspaceId: string) {
    return request<WorkspaceInvitesList>(`/workspace/${workspaceId}/invites`)
  },

  listWorkspaceRooms(workspaceId: string, includeMembers = true) {
    const query = includeMembers ? '?include_members=1' : ''
    return request<WorkspaceRoomsList>(`/workspace/${workspaceId}/rooms${query}`)
  },

  listRoomMembers(roomId: string) {
    return request<WorkspaceRoomMembersList>(`/rooms/${roomId}/members`)
  },

  createWorkspaceRoom(
    workspaceId: string,
    data: {
      name: string
      slug?: string
      room_type?: 'lane' | 'group' | 'direct' | 'channel'
      topic?: string
      avatar_url?: string
      agent_profile_id?: string | null
      member_user_ids?: string[]
      platform_ids?: Record<string, string>
      status?: 'active' | 'archived' | 'locked'
    },
  ) {
    return request<{ ok: boolean; room: WorkspaceRoom }>(`/workspace/${workspaceId}/rooms`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  createHermesProfile(data: {
    name: string
    description?: string
    model?: string
    clone_from?: string
    soul?: string
    display_name?: string
    role?: string
    tagline?: string
    workspace_id?: string
    avatar_url?: string
    avatar_id?: string
  }) {
    return request<{
      ok: boolean
      profile: string
      room_id?: string
      room?: WorkspaceRoom
      runtime_profile?: string
      session_id?: string
      steps?: unknown[]
    }>('/hermes/profiles/create', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  bootstrapAgentFromTemplate(
    template: string,
    data: {
      workspace_id?: string
      model?: string
      soul?: string
      display_name?: string
      role?: string
      tagline?: string
      room_name?: string
      bind_session?: boolean
    },
  ) {
    return request<{
      ok: boolean
      template?: string
      runtime?: string
      room_id?: string
      room?: WorkspaceRoom
      session_id?: string
      steps?: unknown[]
      error?: string
    }>(`/hermes/profiles/${encodeURIComponent(template)}/bootstrap-dm`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  patchRoom(roomId: string, data: { name?: string; topic?: string; avatar_url?: string }) {
    return request<{ ok: boolean; room: WorkspaceRoom }>(`/rooms/${roomId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  createWorkspaceInvite(workspaceId: string, data: { email: string; role?: string }) {
    return request<{ ok: boolean; invite_id: string; token: string; email: string; role: string; expires_at: string; invite_url?: string; email_sent?: boolean }>(`/workspace/${workspaceId}/invites`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  removeWorkspaceMember(workspaceId: string, userId: string) {
    return request<{ ok: boolean; user_id: string; status?: string }>(`/workspace/${workspaceId}/members`, {
      method: 'DELETE',
      body: JSON.stringify({ user_id: userId }),
    })
  },

  addRoomMember(roomId: string, userId: string, role = 'member') {
    return request<{ ok: boolean; membership_id: string }>(`/rooms/${roomId}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, role }),
    })
  },

  removeRoomMember(roomId: string, userId: string) {
    return request<{ ok: boolean }>(`/rooms/${roomId}/members?user_id=${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    })
  },

  acceptWorkspaceInvite(token: string) {
    return request<{ ok: boolean; workspace_id: string; role?: string; membership_id?: string; already_member?: boolean }>(`/invites/${token}/accept`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },

  getMyCohort(workspaceId: string) {
    const query = `?workspace_id=${encodeURIComponent(workspaceId)}`
    return request<{ ok: boolean; workspace_id: string; user_id: string; cohort: CohortAgent[] }>(`/me/cohort${query}`)
  },

  listDelegationGrants(workspaceId: string) {
    return request<{ ok: boolean; workspace_id: string; grants: DelegationGrant[] }>(
      `/workspace/${workspaceId}/delegation-grants`,
    )
  },

  createDelegationGrant(workspaceId: string, granteeUserId: string) {
    return request<{ ok: boolean; grant: DelegationGrant }>(`/workspace/${workspaceId}/delegation-grants`, {
      method: 'POST',
      body: JSON.stringify({ grantee_user_id: granteeUserId, scope: 'agents:delegate' }),
    })
  },

  revokeDelegationGrant(workspaceId: string, grantId: string) {
    return request<{ ok: boolean; id: string }>(`/workspace/${workspaceId}/delegation-grants/${grantId}`, {
      method: 'DELETE',
    })
  },

  logout() {
    return request<{ ok: boolean }>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({}),
    }, false).finally(() => clearStoredSessionTokens())
  },

  getInstallStatus() {
    return request<InstallStatus>('/install/status', {}, false)
  },

  getInstallStack() {
    return request<StackConfig & { ok: boolean }>('/install/stack', {}, false)
  },

  patchInstallStack(data: Record<string, unknown>) {
    return request<StackConfig & { ok: boolean }>('/install/stack', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }, false)
  },

  uploadSiteBrandingAsset(body: { kind: 'og' | 'favicon'; data_base64: string; content_type?: string }) {
    return request<{
      ok: boolean
      kind?: string
      og_image?: string
      favicon?: string
      error?: string
    }>('/install/stack/branding-asset', {
      method: 'POST',
      body: JSON.stringify(body),
    }, false)
  },

  testInstallEmail(email: string) {
    return request<{ ok: boolean; email_sent?: boolean; hint?: string }>('/install/email/test', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }, false)
  },

  testInstallUrl(url: string) {
    return request<{ ok: boolean; error?: string; status?: number; hint?: string; local_ok?: boolean }>(
      '/install/url/test',
      { method: 'POST', body: JSON.stringify({ url }) },
      false,
    )
  },

  getPublishHints(url: string) {
    return request<PublishHints>(
      `/install/publish-hints?url=${encodeURIComponent(url)}`,
      {},
      false,
    )
  },

  setupPublicHttps(url: string) {
    return request<{ ok: boolean; error?: string; log?: string }>(
      '/install/setup-https',
      { method: 'POST', body: JSON.stringify({ url }) },
      false,
    )
  },

  completeInstall(data: Record<string, unknown> = {}) {
    return request<{
      ok: boolean
      user_id: string
      workspace_id: string
      agent_profile_id: string
      runtime_profile: string
      room_id?: string
      session_id?: string
      install_complete: boolean
      error?: string
      steps?: Array<{ step?: string; ok?: boolean; error?: string; skipped?: boolean }>
    }>('/install/complete', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  startGoogleAuth(email = '', inviteToken = '') {
    return request<{ ok: boolean; auth_url: string }>('/auth/google/start', {
      method: 'POST',
      body: JSON.stringify({ email, invite_token: inviteToken }),
    }, false)
  },

  localBootstrap(displayName = 'Owner') {
    return request<SessionProfile & { user_id?: string; session_id?: string; refresh_token?: string }>(
      '/auth/local-bootstrap',
      { method: 'POST', body: JSON.stringify({ display_name: displayName }) },
      false,
    ).then((data) => {
      if (data.session_id) {
        setStoredSessionTokens(data.session_id, data.refresh_token)
      }
      return data
    })
  },

  patchNativeAgent(data: {
    workspace_id: string
    display_name?: string
    tagline?: string
    avatar_url?: string
    avatar_id?: string
    soul?: string
  }) {
    return request<{ ok: boolean; runtime_profile: string }>('/me/native-agent', {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  getAdminUpdates(desktopVersion?: string) {
    const query = desktopVersion ? `?desktop_version=${encodeURIComponent(desktopVersion)}` : ''
    return request<StackUpdatesStatus>(`/admin/updates${query}`, { cache: 'no-store' })
  },

  getApiHealth() {
    return request<WorkframeApiHealth>('/health', { cache: 'no-store' })
  },

  applyAdminUpdate(target: 'hermes' | 'workframe' | 'all') {
    return request<{ ok: boolean; target?: string; log?: string; error?: string }>('/admin/updates/apply', {
      method: 'POST',
      headers: { 'X-Workframe-Local': '1' },
      body: JSON.stringify({ target }),
    })
  },

  restartAdminGateway() {
    return request<{ ok: boolean; target?: string; log?: string; error?: string }>('/admin/stack/restart-gateway', {
      method: 'POST',
      headers: { 'X-Workframe-Local': '1' },
      body: JSON.stringify({}),
    })
  },
}
