import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

type CommandDialogsState = {
  modelOpen: boolean
  helpOpen: boolean
  statusOpen: boolean
  usageOpen: boolean
  profileOpen: boolean
  debugOpen: boolean
  insightsOpen: boolean
  gquotaOpen: boolean
  skillsOpen: boolean
  personalityOpen: boolean
  openModelPicker: () => void
  openHelp: () => void
  openStatus: () => void
  openUsage: () => void
  openProfile: () => void
  openDebug: () => void
  openInsights: () => void
  openGquota: () => void
  openSkills: () => void
  openPersonality: () => void
  closeModelPicker: () => void
  closeHelp: () => void
  closeStatus: () => void
  closeUsage: () => void
  closeProfile: () => void
  closeDebug: () => void
  closeInsights: () => void
  closeGquota: () => void
  closeSkills: () => void
  closePersonality: () => void
}

const CommandDialogsContext = createContext<CommandDialogsState | null>(null)

export function CommandDialogsProvider({ children }: { children: ReactNode }) {
  const [modelOpen, setModelOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [statusOpen, setStatusOpen] = useState(false)
  const [usageOpen, setUsageOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [debugOpen, setDebugOpen] = useState(false)
  const [insightsOpen, setInsightsOpen] = useState(false)
  const [gquotaOpen, setGquotaOpen] = useState(false)
  const [skillsOpen, setSkillsOpen] = useState(false)
  const [personalityOpen, setPersonalityOpen] = useState(false)

  const allClose = () => {
    setModelOpen(false); setHelpOpen(false); setStatusOpen(false); setUsageOpen(false)
    setProfileOpen(false); setDebugOpen(false); setInsightsOpen(false)
    setGquotaOpen(false); setSkillsOpen(false); setPersonalityOpen(false)
  }

  const openModelPicker = useCallback(() => { allClose(); setModelOpen(true) }, [])
  const openHelp = useCallback(() => { allClose(); setHelpOpen(true) }, [])
  const openStatus = useCallback(() => { allClose(); setStatusOpen(true) }, [])
  const openUsage = useCallback(() => { allClose(); setUsageOpen(true) }, [])
  const openProfile = useCallback(() => { allClose(); setProfileOpen(true) }, [])
  const openDebug = useCallback(() => { allClose(); setDebugOpen(true) }, [])
  const openInsights = useCallback(() => { allClose(); setInsightsOpen(true) }, [])
  const openGquota = useCallback(() => { allClose(); setGquotaOpen(true) }, [])
  const openSkills = useCallback(() => { allClose(); setSkillsOpen(true) }, [])
  const openPersonality = useCallback(() => { allClose(); setPersonalityOpen(true) }, [])

  const value = useMemo<CommandDialogsState>(() => ({
    modelOpen, helpOpen, statusOpen, usageOpen, profileOpen, debugOpen, insightsOpen,
    gquotaOpen, skillsOpen, personalityOpen,
    openModelPicker, openHelp, openStatus, openUsage, openProfile, openDebug, openInsights,
    openGquota, openSkills, openPersonality,
    closeModelPicker: () => setModelOpen(false),
    closeHelp: () => setHelpOpen(false),
    closeStatus: () => setStatusOpen(false),
    closeUsage: () => setUsageOpen(false),
    closeProfile: () => setProfileOpen(false),
    closeDebug: () => setDebugOpen(false),
    closeInsights: () => setInsightsOpen(false),
    closeGquota: () => setGquotaOpen(false),
    closeSkills: () => setSkillsOpen(false),
    closePersonality: () => setPersonalityOpen(false),
  }), [modelOpen, helpOpen, statusOpen, usageOpen, profileOpen, debugOpen, insightsOpen,
    gquotaOpen, skillsOpen, personalityOpen,
    openModelPicker, openHelp, openStatus, openUsage, openProfile, openDebug, openInsights,
    openGquota, openSkills, openPersonality])

  return <CommandDialogsContext.Provider value={value}>{children}</CommandDialogsContext.Provider>
}

export function useCommandDialogs(): CommandDialogsState {
  const ctx = useContext(CommandDialogsContext)
  if (!ctx) throw new Error('useCommandDialogs must be used within CommandDialogsProvider')
  return ctx
}
