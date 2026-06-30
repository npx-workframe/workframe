import { useCallback, useState } from 'react'

import { execHermesCommand, execHermesGateway, setHermesModel, type SlashDispatchResult } from '@/lib/hermesCatalogApi'
import { invalidateWorkframeMetaCache } from '@/lib/workframeMetaApi'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'

/**
 * Dispatch a slash command line.
 *
 * Architecture: the BFF resolves the line to a dispatch hint
 * (client / bff / gateway / noop). For `client:*` hints the UI runs
 * the handler directly — no extra round-trip. Gateway-dispatched
 * commands (config writes, gateway control) are deferred to a later
 * slice; the hook returns a noop result so the caller can show a
 * friendly status message.
 *
 * Slice 1 handlers are intentionally limited to ones that don't need
 * a server-side mutation: session restart (`/new`, `/clear`), and
 * local no-ops (`/redraw`, `/quit`). Anything that would require
 * editing the canonical session transcript (`/undo`, `/retry`,
 * `/compress`) is left for Slice 2 with a real BFF endpoint.
 */
export function useSlashDispatcher() {
  const { startNewSession, profile: activeProfile } = useHermesSession()
  const { activeRoom } = useWorkspacePanels()
  const workspaceId = activeRoom?.workspace_id ?? ''
  const [lastResult, setLastResult] = useState<SlashDispatchResult | null>(null)
  const [busy, setBusy] = useState(false)

  const dispatch = useCallback(
    async (line: string): Promise<SlashDispatchResult> => {
      const trimmed = line.trim()
      if (!trimmed.startsWith('/')) {
        const result: SlashDispatchResult = {
          ok: false,
          error: 'not a slash command',
          line: trimmed,
        }
        setLastResult(result)
        return result
      }

      setBusy(true)
      try {
        const result = await execHermesCommand(trimmed)
        if (!result.ok) {
          setLastResult(result)
          return result
        }

        // `/model <id>` — direct set, skip the picker. Lets users set
        // models that aren't in the curated catalog. The BFF does the
        // write; the UI just reflects the new state.
        if (
          result.dispatched === 'client' &&
          result.handler === 'openModelSwitcher' &&
          result.args
        ) {
          try {
            const set = await setHermesModel(result.args, activeProfile, workspaceId)
            if (!set.ok) {
              const fail: SlashDispatchResult = {
                ok: false,
                error: set.error ?? 'model set failed',
                command: result.command,
              }
              setLastResult(fail)
              return fail
            }
            invalidateWorkframeMetaCache()
            const ok: SlashDispatchResult = {
              ok: true,
              dispatched: 'client',
              command: result.command,
              handler: result.handler,
              message: `Model set to ${set.model}`,
            }
            setLastResult(ok)
            return ok
          } catch (err) {
            const fail: SlashDispatchResult = {
              ok: false,
              error: err instanceof Error ? err.message : 'model set failed',
              command: result.command,
            }
            setLastResult(fail)
            return fail
          }
        }

        if (result.dispatched === 'client' && result.handler) {
          switch (result.handler) {
            case 'startNewSession':
            case 'clearMessages':
              await startNewSession()
              break
            case 'openModelSwitcher':
            case 'openHelp':
            case 'openStatus':
              // Dialog-opening handlers: set lastResult with the real
              // handler so the composer's effect routes it to the right
              // dialog. The dialogs already exist; no need to defer.
              break
            case 'noOp':
            default:
              break
          }
        } else if (result.dispatched === 'gateway') {
          // Gateway-routed commands: execute via the BFF gateway proxy
          // which runs `hermes -p {profile} {cmd}` in the gateway container.
          try {
            const gw = await execHermesGateway(result.command + (result.args ? ` ${result.args}` : ''))
            if (gw.ok) {
              const msg = gw.output
                ? `${gw.command}: ${gw.output.slice(0, 200)}`
                : `${gw.command}: done`
              setLastResult({ ok: true, dispatched: 'noop', command: result.command, message: msg })
            } else {
              const msg = gw.error || gw.output || `${gw.command}: failed (rc=${gw.rc})`
              setLastResult({ ok: false, error: msg, command: result.command })
            }
          } catch (err) {
            setLastResult({ ok: false, error: err instanceof Error ? err.message : 'gateway exec failed', command: result.command })
          }
          return result
        }

        setLastResult(result)
        return result
      } finally {
        setBusy(false)
      }
    },
    [startNewSession, activeProfile, workspaceId],
  )

  return { dispatch, lastResult, busy }
}

