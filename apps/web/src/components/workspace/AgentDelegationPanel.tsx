import { useCallback, useEffect, useMemo, useState } from 'react'

import { AgentListItem } from '@/components/settings/AgentListItem'
import { DialogSelect } from '@/components/dialogs/DialogSelect'
import { Button } from '@/components/ui/button'
import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { resolveAgentAvatarUrl } from '@/lib/avatarResolve'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import {
  workframeAuthApi,
  type CohortAgent,
  type DelegationGrant,
  type WorkspaceMember,
} from '@/lib/workframeAuthApi'

type AgentDelegationPanelProps = {
  workspaceId: string
  currentUserId: string
  members: WorkspaceMember[]
  loading?: boolean
  onChanged?: () => void
}

export function AgentDelegationPanel({
  workspaceId,
  currentUserId,
  members,
  loading = false,
  onChanged,
}: AgentDelegationPanelProps) {
  const { closeUserSettings, openAgentSettings } = useWorkspacePanels()
  const [delegationGrants, setDelegationGrants] = useState<DelegationGrant[]>([])
  const [cohort, setCohort] = useState<CohortAgent[]>([])
  const [granteeUserId, setGranteeUserId] = useState('')
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [panelLoading, setPanelLoading] = useState(false)

  const load = useCallback(async () => {
    if (!workspaceId) return
    setPanelLoading(true)
    setError('')
    try {
      const [grantList, cohortPayload] = await Promise.all([
        workframeAuthApi.listDelegationGrants(workspaceId),
        workframeAuthApi.getMyCohort(workspaceId),
      ])
      setDelegationGrants(grantList.grants ?? [])
      setCohort(cohortPayload.cohort ?? [])
      setGranteeUserId('')
    } catch (err) {
      setError(formatWorkframeErrorMessage(err))
    } finally {
      setPanelLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    void load()
  }, [load])

  const memberLabel = useCallback(
    (userId: string) => {
      const member = members.find((row) => row.user_id === userId)
      return member?.display_name || member?.email || userId
    },
    [members],
  )

  const grantableMembers = useMemo(
    () => members.filter((member) => member.user_id !== currentUserId),
    [currentUserId, members],
  )

  const grantableOptions = useMemo(
    () =>
      grantableMembers.map((member) => ({
        value: member.user_id,
        label: member.display_name || member.email || member.user_id,
      })),
    [grantableMembers],
  )

  const grantsGiven = useMemo(
    () => delegationGrants.filter((grant) => grant.grantor_user_id === currentUserId),
    [currentUserId, delegationGrants],
  )

  const grantsReceived = useMemo(
    () => delegationGrants.filter((grant) => grant.grantee_user_id === currentUserId),
    [currentUserId, delegationGrants],
  )

  const showDelegateForm = grantableMembers.length > 0
  const showGrantsGiven = grantsGiven.length > 0
  const showGrantsReceived = grantsReceived.length > 0
  const showGrantsSection = showGrantsGiven || showGrantsReceived

  const createDelegation = async () => {
    if (!workspaceId || !granteeUserId) return
    setBusyId(granteeUserId)
    setError('')
    setStatus('')
    try {
      await workframeAuthApi.createDelegationGrant(workspaceId, granteeUserId)
      await load()
      setStatus('Delegation granted.')
      onChanged?.()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err))
    } finally {
      setBusyId('')
    }
  }

  const revokeDelegation = async (grantId: string) => {
    if (!workspaceId) return
    setBusyId(grantId)
    setError('')
    setStatus('')
    try {
      await workframeAuthApi.revokeDelegationGrant(workspaceId, grantId)
      await load()
      setStatus('Delegation revoked.')
      onChanged?.()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err))
    } finally {
      setBusyId('')
    }
  }

  const openAgent = (agent: CohortAgent) => {
    closeUserSettings()
    openAgentSettings(agent.runtime_slug, agent.display_name)
  }

  const showLoading = loading || panelLoading

  if (showLoading && !cohort.length && !delegationGrants.length) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  if (!cohort.length && !showDelegateForm && !showGrantsSection) {
    return (
      <div className="space-y-3" role="tabpanel">
        {error ? <WorkframeNotice message={error} /> : null}
        <p className="text-sm text-muted-foreground">Open an agent chat to bootstrap your cohort.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6" role="tabpanel">
      {error ? <WorkframeNotice message={error} /> : null}
      {status ? <WorkframeStatusNotice message={status} /> : null}

      {cohort.length ? (
        <section className="wf-settings-section">
          <h3 className="wf-wizard-section__title">Your agents</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {cohort.map((agent) => (
              <AgentListItem
                key={agent.runtime_slug}
                name={agent.display_name}
                tagline={agent.tagline || agent.role}
                avatarUrl={resolveAgentAvatarUrl({
                  avatar_url: agent.avatar_url,
                  avatar_id: agent.avatar_id,
                  profile: agent.template_slug,
                  key: agent.template_slug,
                })}
                onClick={() => openAgent(agent)}
              />
            ))}
          </div>
        </section>
      ) : null}

      {showDelegateForm ? (
        <section className="wf-settings-section">
          <h3 className="wf-wizard-section__title">Delegate to a partner</h3>
          <div className="flex flex-col sm:flex-row gap-2 max-w-md">
            <DialogSelect
              id="wf-user-delegation-grantee"
              className="flex-1"
              value={granteeUserId}
              onValueChange={setGranteeUserId}
              options={grantableOptions}
              placeholder="Workspace member"
              disabled={showLoading || Boolean(busyId)}
            />
            <Button
              type="button"
              disabled={!granteeUserId || Boolean(busyId)}
              onClick={() => void createDelegation()}
            >
              Grant
            </Button>
          </div>
        </section>
      ) : null}

      {showGrantsSection ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {showGrantsGiven ? (
            <section className="wf-settings-section">
              <h3 className="wf-wizard-section__title">Grants you gave</h3>
              <div className="space-y-2">
                {grantsGiven.map((grant) => (
                  <div
                    key={grant.id}
                    className="flex items-center justify-between gap-2 bg-card border border-border rounded-lg p-3"
                  >
                    <strong className="text-sm font-medium truncate">{memberLabel(grant.grantee_user_id)}</strong>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={busyId === grant.id}
                      onClick={() => void revokeDelegation(grant.id)}
                    >
                      Revoke
                    </Button>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {showGrantsReceived ? (
            <section className="wf-settings-section">
              <h3 className="wf-wizard-section__title">Grants you received</h3>
              <div className="space-y-2">
                {grantsReceived.map((grant) => (
                  <div key={grant.id} className="bg-card border border-border rounded-lg p-3">
                    <strong className="text-sm font-medium truncate">{memberLabel(grant.grantor_user_id)}</strong>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
