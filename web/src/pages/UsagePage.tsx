import { useMemo, useState } from 'react'
import { BarChart3, GitCompare, RefreshCw, SlidersHorizontal, X } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Select } from '@/components/ui/Select'
import { resolveUsageWindow, useProjectUsage } from '@/features/usage/hooks'
import { UsageMetricGrid } from '@/features/usage/components/UsageMetricGrid'
import { UsageOperations } from '@/features/usage/components/UsageOperations'
import { UsageStory } from '@/features/usage/components/UsageStory'
import { UsageTrendChart, type UsageTrendMode } from '@/features/usage/components/UsageTrendChart'
import type {
  ProjectUsageBreakdownRow,
  UsageEnvironment,
  UsageGroupBy,
  UsageRange,
} from '@/features/usage/types'
import { cn } from '@/lib/utils'

type UsageLens = 'agent' | 'model' | 'provider'
type UsageComparison = 'none' | 'environment' | 'release'

interface ScopeSelection {
  id: string
  label: string
}

const rangeLabels: Record<UsageRange, string> = {
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  '90d': 'Last 90 days',
}

const environmentLabels: Record<UsageEnvironment, string> = {
  all: 'All environments',
  draft: 'Draft',
  staging: 'Staging',
  production: 'Production',
}

const groupLabels: Record<UsageGroupBy, string> = {
  agent: 'Agent',
  model: 'Model',
  provider: 'Provider',
  environment: 'Environment',
  release: 'Release',
}

function formatDateTime(value: string | null) {
  if (!value) return 'No completed runtime data'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(value))
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US').format(value)
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function ScopeChip({
  label,
  value,
  onRemove,
}: {
  label: string
  value: string
  onRemove: () => void
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-primary/25 bg-primary/10 px-2.5 py-1.5 text-[11px] text-primary-light">
      <span className="text-muted">{label}</span>
      <span className="max-w-[220px] truncate font-medium text-white">{value}</span>
      <button
        type="button"
        onClick={onRemove}
        className="rounded p-0.5 text-muted transition-colors hover:bg-white/10 hover:text-white"
        aria-label={`Remove ${label} filter`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}

export default function UsagePage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const [range, setRange] = useState<UsageRange>('30d')
  const [environment, setEnvironment] = useState<UsageEnvironment>('all')
  const [lens, setLens] = useState<UsageLens>('agent')
  const [comparison, setComparison] = useState<UsageComparison>('none')
  const [trendMode, setTrendMode] = useState<UsageTrendMode>('cost')
  const [agentScope, setAgentScope] = useState<ScopeSelection | null>(null)
  const [modelScope, setModelScope] = useState<ScopeSelection | null>(null)
  const [releaseScope, setReleaseScope] = useState<ScopeSelection | null>(null)
  const [anchor, setAnchor] = useState(() => new Date())

  const groupBy: UsageGroupBy = comparison === 'environment'
    ? 'environment'
    : comparison === 'release'
      ? 'release'
      : lens

  const scopeSummary = [
    rangeLabels[range],
    environmentLabels[environment],
    agentScope?.label ?? 'All agents',
    modelScope?.label,
    releaseScope ? `Release ${releaseScope.label}` : null,
  ].filter(Boolean).join(' · ')

  const analysisSummary = comparison === 'environment'
    ? 'Comparing environments'
    : comparison === 'release'
      ? `Comparing releases for ${agentScope?.label ?? 'the selected agent'}`
      : `Spend analyzed by ${groupLabels[groupBy].toLowerCase()}`

  const contextLabel = `${scopeSummary} · ${analysisSummary}.`

  const params = useMemo(() => {
    if (!projectId) return undefined
    const window = resolveUsageWindow(range, anchor)
    return {
      projectId,
      ...window,
      environment,
      group_by: groupBy,
      agent_id: agentScope?.id,
      provider_model_id: modelScope?.id,
      release_id: releaseScope?.id,
      top_limit: 10,
    }
  }, [
    agentScope?.id,
    anchor,
    environment,
    groupBy,
    modelScope?.id,
    projectId,
    range,
    releaseScope?.id,
  ])

  const usageQuery = useProjectUsage(params)
  const usage = usageQuery.data
  const hasUsage = Boolean(usage && usage.summary.runtime_requests > 0)

  const refresh = () => {
    setAnchor(new Date())
    void usageQuery.refetch()
  }

  const selectEnvironment = (value: UsageEnvironment) => {
    setEnvironment(value)
    if (value !== 'all' && comparison === 'environment') setComparison('none')
    setAnchor(new Date())
  }

  const clearAgentScope = () => {
    setAgentScope(null)
    setReleaseScope(null)
    if (comparison === 'release') setComparison('none')
  }

  const clearAllScopes = () => {
    setEnvironment('all')
    setAgentScope(null)
    setModelScope(null)
    setReleaseScope(null)
    setComparison('none')
    setLens('agent')
    setAnchor(new Date())
  }

  const handleDriverSelect = (row: ProjectUsageBreakdownRow) => {
    if (groupBy === 'agent' && isUuid(row.key)) {
      setAgentScope({ id: row.key, label: row.label })
      setModelScope(null)
      setReleaseScope(null)
      setComparison('none')
      setLens('model')
      return
    }

    if (groupBy === 'model' && isUuid(row.key)) {
      setModelScope({ id: row.key, label: row.label })
      setReleaseScope(null)
      if (agentScope) {
        setComparison('release')
      } else {
        setComparison('none')
        setLens('agent')
      }
      return
    }

    if (groupBy === 'environment' && row.key in environmentLabels) {
      selectEnvironment(row.key as UsageEnvironment)
      setComparison('none')
      return
    }

    if (groupBy === 'release' && isUuid(row.key)) {
      setReleaseScope({ id: row.key, label: row.label })
      setComparison('none')
      setLens(modelScope ? 'provider' : 'model')
    }
  }

  const activeScopeCount = [
    environment !== 'all',
    Boolean(agentScope),
    Boolean(modelScope),
    Boolean(releaseScope),
  ].filter(Boolean).length

  return (
    <ResourcePage
      title="Usage"
      description="Understand what changed, why it changed and where to investigate runtime cost and consumption."
      className="max-w-[1600px]"
      action={(
        <button
          type="button"
          onClick={refresh}
          disabled={usageQuery.isFetching}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-surface/60 px-3 text-xs font-medium text-white transition-colors hover:bg-surface disabled:opacity-50"
        >
          <RefreshCw className={usageQuery.isFetching ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
          Refresh
        </button>
      )}
    >
      <div className="-mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span>Data through <span className="text-white">{formatDateTime(usage?.data_through ?? null)}</span></span>
        {usage?.data_quality.aggregation_lag_seconds !== null && usage?.data_quality.aggregation_lag_seconds !== undefined
          ? <span>· {usage.data_quality.aggregation_lag_seconds}s freshness</span>
          : null}
        <span>·</span>
        <span className="text-primary-light">{contextLabel}</span>
      </div>

      <ResourceToolbar>
        <div className="space-y-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <ResourceTabs
              value={range}
              onChange={(value) => { setRange(value); setAnchor(new Date()) }}
              label="Usage period"
              tabs={[
                { value: '24h', label: 'Last 24 hours' },
                { value: '7d', label: 'Last 7 days' },
                { value: '30d', label: 'Last 30 days' },
                { value: '90d', label: 'Last 90 days' },
              ]}
            />
            <ResourceTabs
              value={environment}
              onChange={selectEnvironment}
              label="Runtime environment"
              tabs={[
                { value: 'all', label: 'All environments' },
                { value: 'draft', label: 'Draft' },
                { value: 'staging', label: 'Staging' },
                { value: 'production', label: 'Production' },
              ]}
            />
          </div>

          <div className="flex flex-col gap-3 border-t border-border/70 pt-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="flex items-center gap-2 text-xs font-medium text-muted">
                <SlidersHorizontal className="h-3.5 w-3.5 text-primary-light" />
                Analyze by
              </div>
              <Select
                id="usage-analyze-by"
                value={lens}
                onChange={(event) => {
                  setLens(event.target.value as UsageLens)
                  setComparison('none')
                }}
                className="min-w-[180px] bg-background/35"
                options={[
                  { value: 'agent', label: 'Agent' },
                  { value: 'model', label: 'Model' },
                  { value: 'provider', label: 'Provider' },
                ]}
              />
              <p className="text-[10px] leading-4 text-muted">
                Environment is a scope filter. Release comparison becomes available after selecting an agent.
              </p>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted">
                <GitCompare className="h-3.5 w-3.5 text-primary-light" />
                Compare
              </div>
              <div className="inline-flex flex-wrap rounded-lg border border-border/80 bg-background/35 p-1">
                <button
                  type="button"
                  onClick={() => setComparison('none')}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                    comparison === 'none' ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
                  )}
                >
                  None
                </button>
                {environment === 'all' && (
                  <button
                    type="button"
                    onClick={() => setComparison('environment')}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      comparison === 'environment' ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
                    )}
                  >
                    Environments
                  </button>
                )}
                {agentScope && !releaseScope && (
                  <button
                    type="button"
                    onClick={() => setComparison('release')}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      comparison === 'release' ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
                    )}
                  >
                    Releases
                  </button>
                )}
              </div>
            </div>
          </div>

          {activeScopeCount > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-border/70 pt-3">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Active scope</span>
              {environment !== 'all' && (
                <ScopeChip label="Environment" value={environmentLabels[environment]} onRemove={() => selectEnvironment('all')} />
              )}
              {agentScope && <ScopeChip label="Agent" value={agentScope.label} onRemove={clearAgentScope} />}
              {modelScope && <ScopeChip label="Model" value={modelScope.label} onRemove={() => setModelScope(null)} />}
              {releaseScope && (
                <ScopeChip
                  label="Release"
                  value={releaseScope.label}
                  onRemove={() => setReleaseScope(null)}
                />
              )}
              <button
                type="button"
                onClick={clearAllScopes}
                className="ml-auto text-[10px] font-medium text-muted transition-colors hover:text-white"
              >
                Clear scope
              </button>
            </div>
          )}
        </div>
      </ResourceToolbar>

      {usageQuery.isLoading ? (
        <LoadingState message="Loading Usage analytics" variant="panel" layout="metrics" />
      ) : usageQuery.isError ? (
        <ErrorState
          error={usageQuery.error}
          onRetry={refresh}
          className="rounded-xl border border-border/80 bg-surface/40 py-10"
        />
      ) : !usage || !hasUsage ? (
        <ResourceEmptyState
          icon={<BarChart3 className="h-4 w-4" />}
          title="No runtime usage in this scope"
          description="Usage appears after an Agent reaches a terminal runtime state. Widen the period or remove a scope filter if executions already exist."
        />
      ) : (
        <div className="space-y-4">
          <UsageStory
            summary={usage.summary}
            breakdown={usage.breakdown}
            groupBy={usage.group_by}
            contextLabel={contextLabel}
          />

          <section>
            <ResourceSectionHeader
              title="Operational scorecard"
              description="Primary outcomes first; supporting consumption metrics remain visible without competing for equal weight."
              count={`${formatNumber(usage.summary.runtime_requests)} runtime requests`}
            />
            <UsageMetricGrid summary={usage.summary} />
          </section>

          <UsageTrendChart
            points={usage.timeseries}
            mode={trendMode}
            bucket={usage.bucket}
            contextLabel={contextLabel}
            onModeChange={setTrendMode}
          />

          <UsageOperations
            breakdown={usage.breakdown}
            composition={usage.composition}
            quality={usage.data_quality}
            executions={usage.top_executions}
            groupBy={usage.group_by}
            contextLabel={contextLabel}
            organizationId={organizationId ?? ''}
            projectId={projectId ?? ''}
            onSelectDriver={handleDriverSelect}
          />
        </div>
      )}
    </ResourcePage>
  )
}
