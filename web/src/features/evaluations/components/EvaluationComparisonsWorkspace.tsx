import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ChevronRight,
  GitCompareArrows,
  Loader2,
  Plus,
} from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  useEvaluationComparison,
  useEvaluationComparisons,
} from '@/features/evaluations/catalogHooks'
import { cn } from '@/lib/utils'
import { EvaluationComparisonView } from './EvaluationComparisonView'

interface Props {
  projectId: string
  entityId: string
  selectedComparisonId?: string | null
  onSelectComparison?: (comparisonId: string) => void
  onCreateComparison?: () => void
}

const active = new Set(['waiting', 'running'])

function targetTitle(value: any, fallback: string) {
  const target = value?.target
  return target ? `${target.display_version}` : fallback
}

export function EvaluationComparisonsWorkspace({
  projectId,
  entityId,
  selectedComparisonId,
  onSelectComparison,
  onCreateComparison,
}: Props) {
  const listQuery = useEvaluationComparisons(projectId, entityId)
  const comparisons = listQuery.data ?? []
  const [internalId, setInternalId] = useState<string | null>(selectedComparisonId || null)
  const comparisonId = selectedComparisonId || internalId || comparisons[0]?.id || null
  const comparisonQuery = useEvaluationComparison(projectId, comparisonId)

  useEffect(() => {
    if (selectedComparisonId) setInternalId(selectedComparisonId)
  }, [selectedComparisonId])

  const select = (id: string) => {
    setInternalId(id)
    onSelectComparison?.(id)
  }

  if (listQuery.isLoading) return <LoadingState message="Loading Comparisons" />
  if (listQuery.isError) return <ErrorState message="Unable to load Comparisons" />

  return (
    <div className="grid min-h-[620px] gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="overflow-hidden rounded-2xl border border-border/80 bg-background/25">
        <div className="border-b border-border/80 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Comparisons</h3>
              <p className="mt-1 text-[11px] leading-4 text-muted">
                Immutable comparisons between two Evaluation Runs.
              </p>
            </div>
            {onCreateComparison ? (
              <Button size="sm" onClick={onCreateComparison}>
                <Plus className="mr-1 h-3.5 w-3.5" />New
              </Button>
            ) : null}
          </div>
        </div>
        <div className="max-h-[690px] overflow-y-auto p-2">
          {comparisons.map((comparison) => {
            const aggregate = comparison.aggregate_result
            const candidate = targetTitle(aggregate?.candidate, 'Candidate')
            const reference = targetTitle(aggregate?.reference, 'Reference')
            const selected = comparison.id === comparisonId
            return (
              <button
                key={comparison.id}
                type="button"
                onClick={() => select(comparison.id)}
                className={cn(
                  'mb-2 w-full rounded-xl border px-3 py-3 text-left',
                  selected
                    ? 'border-primary/40 bg-primary/[0.08]'
                    : 'border-transparent hover:border-border hover:bg-surface/20',
                )}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/80">
                    {active.has(comparison.status)
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />
                      : comparison.status === 'blocked' || comparison.status === 'partial'
                        ? <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />
                        : <GitCompareArrows className="h-3.5 w-3.5 text-muted" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-white">{candidate}</p>
                    <p className="mt-1 truncate text-[10px] text-muted">vs {reference}</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <Badge variant="outline">{comparison.status}</Badge>
                      <span className="text-[10px] text-muted">{comparison.comparison_mode}</span>
                    </div>
                  </div>
                  <ChevronRight className="mt-2 h-3.5 w-3.5 text-muted" />
                </div>
              </button>
            )
          })}
          {!comparisons.length ? (
            <div className="p-8 text-center text-xs leading-5 text-muted">
              No Comparison exists. Start a paired Comparison from Run or compare two compatible historical Runs.
            </div>
          ) : null}
        </div>
      </aside>

      <section className="min-w-0 rounded-2xl border border-border/80 bg-background/20 p-4">
        {!comparisonId ? (
          <div className="flex min-h-[540px] items-center justify-center text-xs text-muted">
            Select or create a Comparison.
          </div>
        ) : comparisonQuery.isLoading ? (
          <LoadingState message="Loading Comparison evidence" />
        ) : comparisonQuery.isError || !comparisonQuery.data ? (
          <ErrorState message="Unable to load this Comparison" />
        ) : (
          <EvaluationComparisonView
            projectId={projectId}
            comparison={comparisonQuery.data}
          />
        )}
      </section>
    </div>
  )
}
