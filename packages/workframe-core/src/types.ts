// Workframe domain types, route/lane definitions, and profile constants.
// Source: workframe-api/server.py, workframe-supervisor/server.py, UI lib/types.

// ---------------------------------------------------------------------------
// Profile / Agent types
// ---------------------------------------------------------------------------

export const SPECIALIST_ROLES = {
  visionary: "Clarifies product purpose, positioning, strategy, user value, and long-term alignment.",
  architect: "Defines system design, technical boundaries, implementation plans, and code-review standards.",
  docs: "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries.",
  dev: "Builds and modifies project files, scripts, tests, and implementation artifacts.",
  research: "Performs technical research, market research, references, competitive analysis, and R&D notes.",
  designer: "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback.",
} as const

export type SpecialistRole = keyof typeof SPECIALIST_ROLES

export const PROFILE_PACKS = {
  native: { label: "Native", profiles: [] as string[] },
  core: { label: "Core", profiles: ["docs", "dev"] },
  product: { label: "Product", profiles: ["docs", "dev", "visionary", "research", "designer"] },
  engineering: { label: "Engineering", profiles: ["docs", "dev", "architect", "research"] },
  vanilla: { label: "Full", profiles: ["docs", "dev", "visionary", "architect", "research", "designer"] },
  full: { label: "Full", profiles: ["docs", "dev", "visionary", "architect", "research", "designer"] },
} as const

export type ProfilePack = keyof typeof PROFILE_PACKS

export interface WorkframeProfile {
  id: string
  role: "native" | SpecialistRole
  displayName: string
  tagline?: string
  avatar?: string
  model?: string
  enabled: boolean
}

// ---------------------------------------------------------------------------
// Route / Lane types
// ---------------------------------------------------------------------------

export type RouteMode = "permanent" | "temporary"

export interface Route {
  profile: string
  lane: string
  displayName: string
  role: string
  mode: RouteMode
  avatar?: string
  enabled: boolean
}

export interface LaneBinding {
  session_id: string
  gateway_session_id?: string
  binding_version: number
}

// ---------------------------------------------------------------------------
// Session types
// ---------------------------------------------------------------------------

export interface Session {
  id: string
  profile: string
  source: string
  client_id: string
  channel?: string
  started_at: string
  ended_at?: string
}

export interface SessionChatMessage {
  id: string
  role: "user" | "assistant" | "tool"
  content: string
  tool_calls?: ToolCall[]
  tool_call_id?: string
  created_at: string
}

export interface ToolCall {
  id: string
  type: "function"
  function: {
    name: string
    arguments: string
  }
}

// ---------------------------------------------------------------------------
// Activity types
// ---------------------------------------------------------------------------

export type ActivityType =
  | "session.created"
  | "session.chat"
  | "tool.call"
  | "tool.result"
  | "profile.spawned"
  | "profile.deleted"
  | "gateway.restart"

export interface ActivityItem {
  id: string
  type: ActivityType
  profile: string
  label: string
  timestamp: string
  tool_call_id?: string
  session_id?: string
  message_id?: string
}

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string
  email_hash: string
  role: "owner" | "admin" | "member"
  display_name?: string
  avatar_url?: string
  created_at: string
}

export interface AuthSession {
  id: string
  user_id: string
  refresh_token_hash: string
  created_at: string
  expires_at: string
  last_used_at?: string
}

export interface OtpChallenge {
  id: string
  email_hash: string
  code_hash: string
  attempts: number
  created_at: string
  expires_at: string
  consumed: boolean
}

// ---------------------------------------------------------------------------
// Workspace / Project types
// ---------------------------------------------------------------------------

export interface Workspace {
  id: string
  slug: string
  name: string
  owner_id: string
  created_at: string
}

export interface WorkspaceMember {
  user_id: string
  workspace_id: string
  role: "owner" | "admin" | "member"
  joined_at: string
}

// ---------------------------------------------------------------------------
// Board / Task types (from board.db)
// ---------------------------------------------------------------------------

export interface BoardTask {
  id: string
  title: string
  body?: string
  status: "todo" | "in_progress" | "done" | "blocked"
  assignee?: string
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Environment / Config
// ---------------------------------------------------------------------------

export interface WorkframeConfig {
  nativeProfile: string
  projectName: string
  auth: {
    secureMode: boolean
    devMode: boolean
    sessionTtlSeconds: number
    otpTtlMinutes: number
  }
  gateway: {
    containerName: string
    port: number
    dashboardPort: number
  }
  api: {
    host: string
    port: number
  }
  smtp: {
    host: string
    port: number
    secure: boolean
    user: string
    from: string
  }
}
