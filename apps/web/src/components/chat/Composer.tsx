import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Paperclip, Send, Square } from 'lucide-react'

import { useCommandDialogs } from '@/contexts/CommandDialogsContext'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { DebugDialog } from '@/components/chat/DebugDialog'
import { GquotaDialog } from '@/components/chat/GquotaDialog'
import { HelpDialog } from '@/components/chat/HelpDialog'
import { InsightsDialog } from '@/components/chat/InsightsDialog'
import { ModelPickerDialog } from '@/components/chat/ModelPickerDialog'
import { ModelSwitcher } from '@/components/chat/ModelSwitcher'
import { PersonalityDialog } from '@/components/chat/PersonalityDialog'
import { ProfileDialog } from '@/components/chat/ProfileDialog'
import { SkillsMenu } from '@/components/chat/SkillsMenu'
import { SlashPalette, type SlashPaletteHandle } from '@/components/chat/SlashPalette'
import { MentionPalette, type MentionAgent, type MentionPaletteHandle } from '@/components/chat/MentionPalette'
import { StatusDialog } from '@/components/chat/StatusDialog'
import { UsageDialog } from '@/components/chat/UsageDialog'
import { Button } from '@/components/ui/button'
import { scrollAreaClass } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { useComposerMinHeight } from '@/hooks/useComposerMinHeight'
import { useSlashDispatcher } from '@/hooks/useSlashDispatcher'
import { mentionTokenAt } from '@/lib/mentionToken'
import { apiStopRun, apiSteerRun, fetchHermesModels, type HermesSkillRow, type SlashDispatchResult } from '@/lib/hermesCatalogApi'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { cn } from '@/lib/utils'

type ComposerProps = {
  onMinHeightChange?: (height: number) => void
  onSend?: (text: string) => void
  onAttachImage?: (file: File) => void
  disabled?: boolean
  turnActive?: boolean
  turnStatus?: string | null
  placeholder?: string
  showModelPicker?: boolean
  mentionAgents?: MentionAgent[]
}

export type ComposerHandle = {
  insertMention: (slug: string) => void
  focus: () => void
}

/** Routes a slash command dispatch result to the right UI surface
 *  (local handler vs. dialog). Keeps the dispatcher pure. */
function routeDispatchResult(
  result: SlashDispatchResult,
  open: { openModelPicker: () => void; openHelp: () => void; openStatus: () => void; openUsage: () => void; openProfile: () => void; openDebug: () => void; openInsights: () => void; openGquota: () => void; openSkills: () => void; openPersonality: () => void },
): boolean {
  if (result.dispatched === 'client' && result.handler) {
    switch (result.handler) {
      case 'openModelSwitcher':
        open.openModelPicker()
        return true
      case 'openHelp':
        open.openHelp()
        return true
      case 'openStatus':
        open.openStatus()
        return true
      case 'openUsage':
        open.openUsage()
        return true
      case 'openProfile':
        open.openProfile()
        return true
      case 'openDebug':
        open.openDebug()
        return true
      case 'openInsights':
        open.openInsights()
        return true
      case 'openGquota':
        open.openGquota()
        return true
      case 'openSkills':
        open.openSkills()
        return true
      case 'openPersonality':
        open.openPersonality()
        return true
      default:
        return false
    }
  }
  return false
}

const ComposerInner = forwardRef<ComposerHandle, ComposerProps>(function ComposerInner({
  onMinHeightChange,
  onSend,
  onAttachImage,
  disabled = false,
  turnActive = false,
  turnStatus = null,
  placeholder = 'Message Workframe Agent…',
  showModelPicker = true,
  mentionAgents = [],
}, ref) {
  const [value, setValue] = useState('')
  const [caret, setCaret] = useState(0)
  const [modelId, setModelId] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const paletteRef = useRef<SlashPaletteHandle>(null)
  const mentionRef = useRef<MentionPaletteHandle>(null)
  const { rootRef, toolbarRef, textareaRef } = useComposerMinHeight(onMinHeightChange)
  const { dispatch, lastResult, busy } = useSlashDispatcher()
  const dialogs = useCommandDialogs()
  const { reloadHistory, profile: activeProfile } = useHermesSession()
  const { activeRoom, openUserSettings } = useWorkspacePanels()
  const workspaceId = activeRoom?.workspace_id ?? ''
  const [hasLlmProvider, setHasLlmProvider] = useState(false)

  useEffect(() => {
    if (!showModelPicker) {
      setModelId('')
      return
    }
    if (!activeProfile) {
      setModelId('')
      return
    }
    void fetchHermesModels(activeProfile, workspaceId)
      .then((res) => {
        if (!res.ok) {
          setModelId('')
          setHasLlmProvider(false)
          return
        }
        setHasLlmProvider(Boolean(res.has_llm_provider))
        if (res.primary) setModelId(res.primary)
        else setModelId('')
      })
      .catch(() => {
        setModelId('')
        setHasLlmProvider(false)
      })
  }, [activeProfile, workspaceId, showModelPicker])

  // The palette shows only while the leading token is a slash command.
  // Once the user types a space (and starts entering args) it closes so
  // they can fill in arguments without the palette obscuring input.
  const paletteOpen = value.startsWith('/') && !/\s/.test(value.slice(1))
  const mentionToken = mentionTokenAt(value, caret)
  const mentionOpen = !paletteOpen && !turnActive && mentionAgents.length > 0 && mentionToken !== null

  useImperativeHandle(ref, () => ({
    insertMention: (slug: string) => {
      const token = `@${slug} `
      setValue((current) => (current.trim() ? `${current.trimEnd()} ${token}` : token))
      setCaret(token.length)
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) return
        el.focus()
        const next = el.value.length
        el.setSelectionRange(next, next)
        setCaret(next)
      })
    },
    focus: () => {
      textareaRef.current?.focus()
    },
  }), [textareaRef])

  function applyMention(agent: MentionAgent) {
    if (!mentionToken) return
    const before = value.slice(0, mentionToken.start)
    const after = value.slice(caret)
    const next = `${before}@${agent.handle} ${after}`
    const nextCaret = before.length + agent.handle.length + 2
    setValue(next)
    setCaret(nextCaret)
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (!el) return
      el.focus()
      el.setSelectionRange(nextCaret, nextCaret)
    })
  }

  function sendCurrent() {
    const text = value.trim()
    if (!text) return
    setValue('')
    // When agent is working, treat regular text as a steer command
    if (turnActive) {
      void apiSteerRun(activeProfile, text)
    } else {
      onSend?.(text)
    }
  }

  async function submit() {
    const text = value.trim()
    if (!text) return
    if (text.startsWith('/')) {
      await dispatch(text)
      setValue('')
      return
    }
    sendCurrent()
  }

  function handleImageFile(file: File | null | undefined) {
    if (!file || !file.type.startsWith('image/')) return
    onAttachImage?.(file)
  }

  // Show the last dispatch result briefly, then clear it. Keeps the
  // turn-status line as the single feedback channel so we don't introduce
  // a parallel toast system in this slice.
  const [flash, setFlash] = useState<string | null>(null)
  useEffect(() => {
    if (!lastResult) return
    const result = lastResult
    const msg = result.ok
      ? (result.message ?? `Ran ${result.command}`)
      : (result.error ?? 'Command failed')
    setFlash(msg)
    // Route dialog-opening through the same effect so the slash
    // palette (click) and the composer textarea (Enter / submit)
    // both end up in the same place. The dispatcher hook applies
    // any local state mutation (e.g. startNewSession) before the
    // result is set; the composer's job is to open dialogs.
    if (result.ok) routeDispatchResult(result, dialogs)
    // Model changes invalidate the meta cache upstream, so the next
    // fetch here sees the new value. Re-fetching on every command would
    // hammer the BFF; the gate keeps it to model-affecting commands.
    if (result.ok && result.command === '/model') {
      void fetchHermesModels(activeProfile, workspaceId)
        .then((m) => m.primary && setModelId(m.primary))
        .catch(() => undefined)
    }
    const t = window.setTimeout(() => setFlash(null), 3500)
    return () => window.clearTimeout(t)
    // Note: deps are [lastResult] only. Adding `dialogs` here would
    // re-fire the routing every time the dialog context value
    // changes — including the case where this very effect just
    // toggled a dialog open. That would create a feedback loop
    // (route opens dialog → dialog closes via user → context changes
    // → effect re-runs → re-opens dialog). The dialog handlers are
    // stable via useCallback in CommandDialogsContext, so capturing
    // them once from the closure is correct.
  }, [lastResult])

  return (
    <div ref={rootRef} className="wf-composer">
      {paletteOpen ? (
        <SlashPalette
          ref={paletteRef}
          anchor={textareaRef.current}
          isOpen={paletteOpen}
          value={value}
          onPick={(cmd) => {
            if (cmd.args_hint && cmd.args_hint.length > 0) {
              setValue(`${cmd.name} `)
              textareaRef.current?.focus()
            } else {
              void dispatch(cmd.name)
              setValue('')
            }
          }}
        />
      ) : null}
      {mentionOpen && mentionToken ? (
        <MentionPalette
          ref={mentionRef}
          anchor={textareaRef.current}
          isOpen={mentionOpen}
          query={mentionToken.query}
          agents={mentionAgents}
          onPick={applyMention}
        />
      ) : null}
      {turnStatus || flash ? (
        <p className="wf-composer__turn-status" role="status" aria-live="polite">
          {flash ?? turnStatus}
        </p>
      ) : null}

      {/* When agent is working: textarea becomes steer input, send button becomes stop.
          Same composer, same textarea — just a different mode. */}
      {turnActive ? (
        <div className="wf-composer__working-indicator-row">
          <div className="wf-composer__working-indicator" />
          <span className="wf-composer__working-label">Working…</span>
        </div>
      ) : null}

      <Textarea
        ref={textareaRef}
        className={cn('wf-composer__input', scrollAreaClass, 'wf-scroll--vertical')}
        rows={1}
        placeholder={turnActive ? 'Steer the agent…' : placeholder}
        value={value}
        disabled={disabled || busy}
        onChange={(event) => {
          setValue(event.target.value)
          setCaret(event.target.selectionStart ?? event.target.value.length)
        }}
        onSelect={(event) => {
          const target = event.currentTarget
          setCaret(target.selectionStart ?? target.value.length)
        }}
        onClick={(event) => {
          const target = event.currentTarget
          setCaret(target.selectionStart ?? target.value.length)
        }}
        onPaste={(event) => {
          const file = event.clipboardData?.files?.[0]
          if (file?.type.startsWith('image/')) {
            event.preventDefault()
            handleImageFile(file)
          }
        }}
        onKeyDown={(event) => {
          if (mentionOpen) {
            if (event.key === 'Tab') {
              event.preventDefault()
              mentionRef.current?.accept()
              return
            }
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              mentionRef.current?.down()
              return
            }
            if (event.key === 'ArrowUp') {
              event.preventDefault()
              mentionRef.current?.up()
              return
            }
          }
          if (paletteOpen) {
            if (event.key === 'Tab') {
              event.preventDefault()
              paletteRef.current?.accept()
              return
            }
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              paletteRef.current?.down()
              return
            }
            if (event.key === 'ArrowUp') {
              event.preventDefault()
              paletteRef.current?.up()
              return
            }
          }
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            void submit()
          }
        }}
        aria-label={turnActive ? 'Steer input' : 'Message input'}
      />

      <div ref={toolbarRef} className="wf-composer__toolbar">
        <div className="wf-composer__toolbar-start">
          {showModelPicker ? (
            <ModelSwitcher
              modelId={modelId}
              hasProvider={hasLlmProvider}
              onConnectProvider={() => openUserSettings('connect')}
            />
          ) : null}
          <SkillsMenu
            onPick={(skill: HermesSkillRow) => {
              // Skills are themselves slash commands; dispatching
              // them through the same pipeline as /new means the
              // BFF / gateway / approval flow all treat them
              // uniformly.
              void dispatch(`/${skill.name}`)
            }}
          />
        </div>

        <div className="wf-composer__actions">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="wf-composer__file-input"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              handleImageFile(event.target.files?.[0])
              event.target.value = ''
            }}
          />
          <Button
            type="button"
            variant="toolbar"
            size="toolbarIcon"
            aria-label="Attach image"
            disabled={disabled || !onAttachImage}
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="toolbar"
            size="toolbarIcon"
            className={cn('wf-tool-btn--send', turnActive && 'wf-tool-btn--stop')}
            disabled={disabled || (!turnActive && !value.trim())}
            onClick={() => {
              if (turnActive) {
                void apiStopRun(activeProfile)
                setValue('')
              } else {
                void submit()
              }
            }}
            aria-label={turnActive ? 'Stop the agent' : 'Send message'}
          >
            {turnActive ? <Square aria-hidden="true" /> : <Send aria-hidden="true" />}
          </Button>
        </div>
      </div>

      <ModelPickerDialog
        open={showModelPicker && dialogs.modelOpen}
        onOpenChange={dialogs.closeModelPicker}
        profile={activeProfile}
        workspaceId={workspaceId}
        onConnectProvider={() => openUserSettings('connect')}
        onChanged={(model) => {
          setModelId(model)
          void reloadHistory().catch(() => undefined)
        }}
      />
      <HelpDialog open={dialogs.helpOpen} onOpenChange={dialogs.closeHelp} />
      <StatusDialog open={dialogs.statusOpen} onOpenChange={dialogs.closeStatus} />
      <UsageDialog open={dialogs.usageOpen} onOpenChange={dialogs.closeUsage} />
      <ProfileDialog open={dialogs.profileOpen} onOpenChange={dialogs.closeProfile} />
      <DebugDialog open={dialogs.debugOpen} onOpenChange={dialogs.closeDebug} />
      <InsightsDialog open={dialogs.insightsOpen} onOpenChange={dialogs.closeInsights} />
      <GquotaDialog open={dialogs.gquotaOpen} onOpenChange={dialogs.closeGquota} />
      <PersonalityDialog open={dialogs.personalityOpen} onOpenChange={dialogs.closePersonality} />
    </div>
  )
})

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(props, ref) {
  return <ComposerInner {...props} ref={ref} />
})
