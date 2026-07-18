import { describe, expect, it } from 'vitest'
import { adaptProjectOverview, formatCost, formatLatency, formatPercent } from './adapters'
import { projectOverviewFixture } from './fixtures'

function cloneFixture() {
  return structuredClone(projectOverviewFixture)
}

describe('adaptProjectOverview', () => {
  it('maps Agent Runs and Network Runs to the overview view model', () => {
    const model = adaptProjectOverview(cloneFixture())

    expect(model.metrics.map((metric) => metric.label)).toEqual([
      'Agent Runs',
      'Network Runs',
      'Runtime Cost',
      'Avg Agent Run',
      'Avg Network Run',
      'Run Health',
    ])
    expect(model.series).toHaveLength(2)
    expect(model.releases[0]?.environmentLabel).toBe('Production')
    expect(model.runs.map((run) => run.subtitle)).toContain('Agent Run')
    expect(model.runs.map((run) => run.subtitle)).toContain('Network Run')
    expect(model.environmentTotal).toBe(3)
    expect(model.isExecutionEmpty).toBe(false)
  })

  it('does not coerce unknown Run values to zero', () => {
    const fixture = cloneFixture()
    fixture.summary.avg_agent_run_duration_ms = null
    fixture.summary.agent_run_success_rate = null
    fixture.summary.agent_run_cost_usd = null
    fixture.summary.unknown_agent_run_cost_count = 2
    fixture.recent_traces[0]!.latency_ms = null
    fixture.recent_traces[0]!.total_tokens = null
    fixture.recent_traces[0]!.cost_usd = null
    fixture.recent_traces[0]!.cost_known = false

    const model = adaptProjectOverview(fixture)
    const agentRun = model.runs.find((run) => run.kind === 'agent')

    expect(formatLatency(null)).toBe('—')
    expect(formatPercent(null)).toBe('—')
    expect(formatCost(null)).toBe('Unknown')
    expect(model.metrics.find((metric) => metric.label === 'Runtime Cost')?.value).toBe('Unknown')
    expect(agentRun?.durationLabel).toBe('—')
    expect(agentRun?.tokenLabel).toBe('—')
    expect(agentRun?.costLabel).toBe('Unknown')
  })

  it('preserves legitimate zero values and capability flags', () => {
    const fixture = cloneFixture()
    fixture.summary.agent_runs = 0
    fixture.summary.network_runs = 0
    fixture.summary.avg_agent_run_duration_ms = 0
    fixture.summary.agent_run_success_rate = 0
    fixture.summary.agent_run_cost_usd = 0
    fixture.timeseries = []
    fixture.capabilities.sessions_jobs = true

    const model = adaptProjectOverview(fixture)

    expect(formatLatency(0)).toContain('0')
    expect(formatPercent(0)).toBe('0%')
    expect(formatCost(0)).not.toBe('Unknown')
    expect(model.isExecutionEmpty).toBe(true)
    expect(model.capabilities.sessions_jobs).toBe(true)
  })
})
