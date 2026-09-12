import { useMemo, useState } from 'react'
import { BarChart3, RefreshCw, SlidersHorizontal, X } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { Button, Select } from '@woobe/ui'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { useNetworks } from '@/features/network/hooks'
import { resolveUsageWindow, useProjectUsage } from '@/features/usage/hooks'
import { UsageMetricGrid } from '@/features/usage/components/UsageMetricGrid'
import { UsageOperations } from '@/features/usage/components/UsageOperations'
import { UsageTrendChart, type UsageTrendMode } from '@/features/usage/components/UsageTrendChart'
import type {
  ProjectUsageBreakdownRow,
  UsageEnvironment,
  UsageGroupBy,
  UsageOperation,
  UsageRange,
} from '@/features/usage/types'

type UsageLens = Extract<UsageGroupBy, 'agent' | 'network' | 'model' | 'provider'>

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

const operationLabels: Record<UsageOperation, string> = {
  all: 'All operations',
  agent: 'Direct Agent Runs',
  network: 'Network Runs',
}

const groupLabels: Record<UsageLens, string> = {
  agent: 'Agent',
  network: 'Network',
  model: 'Model',
  provider: 'Provider',
}

function formatDateTime(value: string | null) {
  if (!value) return 'No completed Run data'
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
    <span className="inline-flex h-[28px] items-center gap-1.5 rounded-technical border border-primary/25 bg-primary/[0.07] px-2 font-mono text-[8px] text-primary-light">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[220px] truncate font-medium text-slate-100">{value}</span>
      <button
        type="button"
        onClick={onRemove}
        className="flex h-4 w-4 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50"
        aria-label={`Remove ${label} filter`}
      >
        <X className="h-2.5 w-2.5" />
      </button>
    </span>
  )
}

export default function UsagePage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const networksQuery = useNetworks(projectId)
  const [range, setRange] = useState<UsageRange>('30d')
  const [environment, setEnvironment] = useState<UsageEnvironment>('all')
  const [operation, setOperation] = useState<UsageOperation>('all')
  const [lens, setLens] = useState<UsageLens>('agent')
  const [trendMode, setTrendMode] = useState<UsageTrendMode>('cost')
  const [networkScope, setNetworkScope] = useState<ScopeSelection | null>(null)
  const [agentScope, setAgentScope] = useState<ScopeSelection | null>(null)
  const [modelScope, setModelScope] = useState<ScopeSelection | null>(null)
  const [anchor, setAnchor] = useState(() => new Date())

  const scopeSummary = [
    rangeLabels[range],
    environmentLabels[environment],
    operationLabels[operation],
    networkScope?.label,
    agentScope?.label,
    modelScope?.label,
    `By ${groupLabels[lens]}`,
  ].filter(Boolean).join(' · ')

  const params = useMemo(() => {
    if (!projectId) return undefined
    const window = resolveUsageWindow(range, anchor)
    return {
      projectId,
      ...window,
      environment,
      operation,
      group_by: lens,
      network_id: networkScope?.id,
      agent_id: agentScope?.id,
      provider_model_id: modelScope?.id,
      top_limit: 10,
    }
  }, [
    agentScope?.id,
    anchor,
    environment,
    lens,
    modelScope?.id,
    networkScope?.id,
    operation,
    projectId,
    range,
  ])

  const usageQuery = useProjectUsage(params)
  const usage = usageQuery.data
  const hasUsage = Boolean(usage && (usage.summary.agent_runs > 0 || usage.summary.network_runs > 0))

  const refresh = () => {
    setAnchor(new Date())
    void usageQuery.refetch()
  }

  const selectEnvironment = (value: UsageEnvironment) => {
    setEnvironment(value)
    setAnchor(new Date())
  }

  const selectOperation = (value: UsageOperation) => {
    setOperation(value)
    if (value === 'agent') {
      setNetworkScope(null)
      if (lens === 'network') setLens('agent')
    }
    if (value === 'network' && operation !== 'network') setLens('network')
    setAnchor(new Date())
  }

  const selectNetwork = (networkId: string) => {
    if (!networkId) {
      setNetworkScope(null)
      setAnchor(new Date())
      return
    }
    const network = (networksQuery.data ?? []).find((item) => item.id === networkId)
    setNetworkScope(network ? { id: network.id, label: network.name } : null)
    setAnchor(new Date())
  }

  const clearAllScopes = () => {
    setEnvironment('all')
    setOperation('all')
    setNetworkScope(null)
    setAgentScope(null)
    setModelScope(null)
    setLens('agent')
    setAnchor(new Date())
  }

  const handleDriverSelect = (row: ProjectUsageBreakdownRow) => {
    if (!isUuid(row.key)) return
    if (lens === 'agent') {
      setAgentScope({ id: row.key, label: row.label })
      setModelScope(null)
    } else if (lens === 'network') {
      selectNetwork(row.key)
    } else if (lens === 'model') {
      setModelScope({ id: row.key, label: row.label })
    }
  }

  const activeScopeCount = [
    environment !== 'all',
    operation !== 'all',
    Boolean(networkScope),
    Boolean(agentScope),
    Boolean(modelScope),
  ].filter(Boolean).length

  const lensOptions: Array<{ value: UsageLens; label: string }> = operation === 'agent'
    ? [
        { value: 'agent', label: 'Analyze by Agent' },
        { value: 'provider', label: 'Analyze by Provider' },
        { value: 'model', label: 'Analyze by Model' },
      ]
    : [
        { value: 'network', label: 'Analyze by Network' },
        { value: 'agent', label: 'Analyze by Agent' },
        { value: 'provider', label: 'Analyze by Provider' },
        { value: 'model', label: 'Analyze by Model' },
      ]

  return (
    <ResourcePage
      title="Usage"
      description="Costs and operational efficiency for this Project."
      className="max-w-[1600px]"
      action={(
        <Button type="button" variant="outline" onClick={refresh} disabled={usageQuery.isFetching}>
          <RefreshCw className={usageQuery.isFetching ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
          Refresh
        </Button>
      )}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border border-border bg-control/25 px-3 py-2 font-mono text-[8px] text-muted-foreground">
        <span>Data through <span className="text-slate-100">{formatDateTime(usage?.data_through ?? null)}</span></span>
        {usage?.data_quality.aggregation_lag_seconds !== null && usage?.data_quality.aggregation_lag_seconds !== undefined
          ? <span>· {usage.data_quality.aggregation_lag_seconds}s freshness</span>
          : null}
        <span>·</span>
        <span className="text-primary-light">{scopeSummary}</span>
      </div>

      <ResourceToolbar>
        <div className="space-y-3">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
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

          <div className="border-t border-border/70 pt-3">
            <ResourceTabs
              value={operation}
              onChange={selectOperation}
              label="Operation type"
              tabs={[
                { value: 'all', label: 'All operations' },
                { value: 'agent', label: 'Direct Agent Runs' },
                { value: 'network', label: 'Network Runs' },
              ]}
            />
          </div>

          <div className="flex flex-col gap-2.5 border-t border-border/70 pt-3 lg:flex-row lg:items-center">
            <div className="flex shrink-0 items-center gap-1.5 font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">
              <SlidersHorizontal className="h-3.5 w-3.5 text-primary-light" />
              Scope and attribution
            </div>
            {operation !== 'agent' ? (
              <Select
                id="usage-network-scope"
                value={networkScope?.id ?? ''}
                onChange={(event) => selectNetwork(event.target.value)}
                className="min-w-[200px]"
                options={[
                  { value: '', label: 'All Networks' },
                  ...(networksQuery.data ?? []).map((network) => ({ value: network.id, label: network.name })),
                ]}
              />
            ) : null}
            <Select
              id="usage-analyze-by"
              value={lens}
              onChange={(event) => setLens(event.target.value as UsageLens)}
              className="min-w-[190px]"
              options={lensOptions}
            />
            <p className="font-sans text-[10px] leading-4 text-muted-foreground">
              Runs define the operation. Provider and Model only explain where the Run cost came from.
            </p>
          </div>

          {activeScopeCount > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5 border-t border-border/70 pt-3">
              <span className="font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">Active scope</span>
              {environment !== 'all' ? <ScopeChip label="Environment" value={environmentLabels[environment]} onRemove={() => selectEnvironment('all')} /> : null}
              {operation !== 'all' ? <ScopeChip label="Operation" value={operationLabels[operation]} onRemove={() => selectOperation('all')} /> : null}
              {networkScope ? <ScopeChip label="Network" value={networkScope.label} onRemove={() => selectNetwork('')} /> : null}
              {agentScope ? <ScopeChip label="Agent" value={agentScope.label} onRemove={() => setAgentScope(null)} /> : null}
              {modelScope ? <ScopeChip label="Model" value={modelScope.label} onRemove={() => setModelScope(null)} /> : null}
              <Button type="button" size="sm" variant="ghost" className="ml-auto" onClick={clearAllScopes}>
                Clear scope
              </Button>
            </div>
          ) : null}
        </div>
      </ResourceToolbar>

      {usageQuery.isLoading ? (
        <LoadingState message="Loading Usage analytics" variant="panel" layout="metrics" />
      ) : usageQuery.isError ? (
        <ErrorState error={usageQuery.error} onRetry={refresh} className="rounded-container border border-border bg-surface/70 py-10" />
      ) : !usage || !hasUsage ? (
        <ResourceEmptyState
          icon={<BarChart3 className="h-4 w-4" />}
          title="No Run usage in this scope"
          description="Usage appears after an Agent Run or Network Run reaches a terminal state. Widen the period or remove a scope filter if executions already exist."
        />
      ) : (
        <div className="space-y-4">
          <section>
            <ResourceSectionHeader
              title="Operational scorecard"
              description="Run volume, unit economics, reliability and pricing coverage."
              count={`${formatNumber(usage.summary.agent_runs)} Agent Runs · ${formatNumber(usage.summary.network_runs)} Network Runs`}
            />
            <UsageMetricGrid summary={usage.summary} />
          </section>

          <UsageTrendChart
            points={usage.timeseries}
            mode={trendMode}
            bucket={usage.bucket}
            contextLabel={scopeSummary}
            onModeChange={setTrendMode}
          />

          <UsageOperations
            breakdown={usage.breakdown}
            composition={usage.composition}
            quality={usage.data_quality}
            executions={usage.top_executions}
            groupBy={usage.group_by}
            contextLabel={scopeSummary}
            workspaceId={workspaceId ?? ''}
            projectId={projectId ?? ''}
            onSelectDriver={handleDriverSelect}
          />
        </div>
      )}
    </ResourcePage>
  )
}
