import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, History } from 'lucide-react'
import { toast } from 'sonner'
import {
  Badge,
  Button,
  Dialog,
  EmptyStatePanel,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'

import { getRelease } from '@/features/agents/api'
import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import { activationLabel, describeReleaseChanges, formatReleaseDate, sessionModeLabel } from './releasePresentation'

type ActivationWithDescription = AgentReleaseActivation & { change_description?: string | null }
type ProductionChangesModalProps = {
  open: boolean
  agentId: string
  activations: AgentReleaseActivation[]
  releases: AgentRelease[]
  initialActivation?: AgentReleaseActivation | null
  onClose: () => void
}

function badgeVariant(action: AgentReleaseActivation['action']) {
  if (action === 'rollback') return 'warning' as const
  if (action === 'deploy') return 'success' as const
  return 'secondary' as const
}

export function ProductionChangesModal({
  open,
  agentId,
  activations: rawActivations,
  releases,
  initialActivation = null,
  onClose,
}: ProductionChangesModalProps) {
  const activations = rawActivations as ActivationWithDescription[]
  const releasesById = useMemo(() => new Map(releases.map((release) => [release.id, release])), [releases])
  const [selected, setSelected] = useState<ActivationWithDescription | null>(null)
  const [currentRelease, setCurrentRelease] = useState<AgentRelease | null>(null)
  const [previousRelease, setPreviousRelease] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [initialApplied, setInitialApplied] = useState(false)

  const view = useCallback(async (activation: ActivationWithDescription) => {
    setLoadingId(activation.id)
    try {
      const [current, previous] = await Promise.all([
        getRelease(agentId, activation.release_id),
        activation.previous_release_id ? getRelease(agentId, activation.previous_release_id) : Promise.resolve(null),
      ])
      setSelected(activation)
      setCurrentRelease(current)
      setPreviousRelease(previous)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Production change')
    } finally {
      setLoadingId(null)
    }
  }, [agentId])

  useEffect(() => {
    if (!open) {
      setInitialApplied(false)
      return
    }
    if (initialActivation && !initialApplied) {
      setInitialApplied(true)
      void view(initialActivation as ActivationWithDescription)
    }
  }, [initialActivation, initialApplied, open, view])

  const close = () => {
    setSelected(null)
    setCurrentRelease(null)
    setPreviousRelease(null)
    setLoadingId(null)
    setInitialApplied(false)
    onClose()
  }
  const back = () => {
    setSelected(null)
    setCurrentRelease(null)
    setPreviousRelease(null)
  }
  const changes = describeReleaseChanges(previousRelease, currentRelease)

  return (
    <Dialog
      open={open}
      onClose={close}
      title={selected ? 'Production change details' : 'Latest Production Changes'}
      className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex shrink-0 items-center gap-ui-sm border-b border-border bg-background/20 px-ui-lg py-ui-sm">
          {selected ? (
            <Button type="button" size="iconSm" variant="ghost" onClick={back} aria-label="Back to Production changes">
              <ArrowLeft className="h-icon w-icon" />
            </Button>
          ) : null}
          <p className="font-sans text-product-caption text-muted-foreground">
            {selected ? 'Operational history for the selected Production activation.' : 'Deployments, reactivations and rollbacks from newest to oldest.'}
          </p>
        </div>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-lg">
          {selected && currentRelease ? (
            <div className="grid gap-ui-md">
              <SectionBlock title="Production transition" density="compact">
                <div className="flex flex-wrap items-center gap-ui-sm">
                  <Badge variant={badgeVariant(selected.action)} size="compact">{activationLabel(selected.action)}</Badge>
                  <span className="font-mono text-system-control text-muted-foreground">{previousRelease?.version ?? 'No Production'}</span>
                  <ArrowRight className="h-icon w-icon text-muted-foreground" />
                  <span className="font-mono text-system-control font-semibold text-accent-foreground">{currentRelease.version}</span>
                </div>
                <p className="mt-ui-sm font-mono text-system-meta text-muted-foreground">{formatReleaseDate(selected.created_at)}</p>
              </SectionBlock>

              <SectionBlock title="Audit note" density="compact">
                <p className="whitespace-pre-wrap font-sans text-product-small leading-5 text-accent-foreground/85">
                  {selected.change_description || 'No audit note was recorded for this historical activation.'}
                </p>
              </SectionBlock>

              <SectionBlock title="What changed" density="compact">
                <div className="grid gap-ui-xs">
                  {changes.map((change) => <TechnicalListItem key={change} label={change} />)}
                </div>
              </SectionBlock>

              {currentRelease.release_notes ? (
                <SectionBlock title="Release description" density="compact">
                  <p className="whitespace-pre-wrap font-sans text-product-small leading-5 text-accent-foreground/85">{currentRelease.release_notes}</p>
                </SectionBlock>
              ) : null}

              <SectionBlock title="Resulting Production" density="compact">
                <div className="grid gap-ui-xs sm:grid-cols-2">
                  {[
                    ['Release', currentRelease.version],
                    ['Session Mode', sessionModeLabel(currentRelease.session_mode)],
                    ['Provider', currentRelease.provider ?? '—'],
                    ['Model', currentRelease.model ?? '—'],
                  ].map(([label, value]) => (
                    <TechnicalListItem key={label} label={label} description={value} />
                  ))}
                </div>
              </SectionBlock>
            </div>
          ) : activations.length ? (
            <div className="grid gap-ui-xs">
              {activations.map((activation) => {
                const release = releasesById.get(activation.release_id) ?? null
                const previous = activation.previous_release_id ? releasesById.get(activation.previous_release_id) ?? null : null
                const summary = activation.change_description || describeReleaseChanges(previous, release)[0]
                return (
                  <TechnicalListItem
                    key={activation.id}
                    label={summary}
                    description={formatReleaseDate(activation.created_at)}
                    leading={<History className="h-icon w-icon text-muted-foreground" />}
                    meta={(
                      <>
                        <Badge variant={badgeVariant(activation.action)} size="compact">{activationLabel(activation.action)}</Badge>
                        <span>{previous?.version ?? 'No Production'}</span>
                        <ArrowRight className="h-icon-sm w-icon-sm" />
                        <span className="text-accent-foreground">{release?.version ?? activation.release_id.slice(0, 8)}</span>
                      </>
                    )}
                    trailing={loadingId === activation.id ? <Badge variant="outline" size="compact">Loading…</Badge> : <Badge variant="outline" size="compact">View</Badge>}
                    disabled={Boolean(loadingId && loadingId !== activation.id)}
                    onClick={() => { void view(activation) }}
                  />
                )
              })}
            </div>
          ) : (
            <EmptyStatePanel
              compact
              icon={<History className="h-icon-lg w-icon-lg" />}
              title="No Production changes recorded"
              description="Deployments, reactivations and rollbacks will appear here."
            />
          )}
        </div>

        <div className="flex shrink-0 items-center justify-end border-t border-border bg-surface/95 px-ui-lg py-ui-md">
          <Button size="sm" variant="outline" onClick={close}>Close</Button>
        </div>
      </div>
    </Dialog>
  )
}
