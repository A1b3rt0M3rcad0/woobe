import { describe, expect, it } from 'vitest'
import { adaptProjectOverview, formatCost, formatLatency, formatPercent } from './adapters'
import { projectOverviewFixture } from './fixtures'

function cloneFixture() {
  return structuredClone(projectOverviewFixture)
}

describe('adaptProjectOverview', () => {
  it('does not round a positive microcost into a displayed zero', () => {
    expect(formatCost(0.00002898)).toBe('< $0.0001')
    expect(formatCost(0.0000000001)).toBe('< $0.0001')
    expect(formatCost(0)).toBe('$0.00')
    expect(formatCost(0.00002898, false)).toBe('Unknown')
  })
  it('includes terminal uncertain Runs in errors without inventing their cost', () => {
    const fixture = cloneFixture()
    Object.assign(fixture.summary, { agent_runs: 1, terminal_agent_runs: 1, successful_agent_runs: 0,
      failed_agent_runs: 0, timed_out_agent_runs: 0, uncertain_agent_runs: 1,
      agent_run_cost_usd: null, priced_agent_runs: 0, unknown_agent_run_cost_count: 1,
      unknown_token_usage_agent_runs: 1 })
    Object.assign(fixture.timeseries[0]!, { agent_run_failed: 0, agent_run_timed_out: 0, agent_run_uncertain: 1 })
    const model = adaptProjectOverview(fixture)
    expect(model.issues.totalAgentErrors).toBe(1)
    expect(model.reliability.agent.uncertain).toBe(1)
    expect(model.series[0]?.agentErrors).toBe(1)
    expect(model.metrics.find((metric) => metric.label === 'Runtime Cost')?.value).toBe('Unknown')
  })
  it('explains missing pricing separately from incomplete token usage', () => {
    const fixture = cloneFixture()
    fixture.summary.agent_run_cost_usd = null
    fixture.summary.terminal_agent_runs = 58
    fixture.summary.priced_agent_runs = 0
    fixture.summary.unknown_agent_run_cost_count = 58
    fixture.summary.unknown_pricing_agent_runs = 57
    fixture.summary.unknown_token_usage_agent_runs = 1
    fixture.recent_traces[0]!.cost_known = false
    fixture.recent_traces[0]!.cost_reason = 'Provider model has no active pricing configured'
    const model = adaptProjectOverview(fixture)
    const cost = model.metrics.find((metric) => metric.label === 'Runtime Cost')
    expect(cost?.value).toBe('Unknown')
    expect(cost?.detail).toBe('0/58 Runs priced · Partial')
    expect(cost?.costHelp?.description).toContain('57 Runs without frozen prices')
    expect(cost?.costHelp?.description).toContain('1 incomplete token usage')
    expect(cost?.costHelp?.reviewPricing).toBe(true)
    expect(model.runs.find((run) => run.kind === 'agent')?.costDetail).toContain('no active pricing')
  })

  it('labels the recorded subtotal when only part of the Runs have prices', () => {
    const fixture = cloneFixture()
    fixture.summary.agent_run_cost_usd = 0.1
    fixture.summary.unknown_agent_run_cost_count = 1
    const model = adaptProjectOverview(fixture)
    const cost = model.metrics.find((metric) => metric.label === 'Runtime Cost')
    expect(cost?.detail).toContain('Partial')
    expect(cost?.costHelp?.description).toContain('1 without cost evidence')
    expect(cost?.costHelp?.reviewPricing).toBe(false)
  })
  it('maps the operational story to the Overview view model', () => {
    const model = adaptProjectOverview(cloneFixture())
    const averageRunTimeMetric = model.metrics[model.metrics.length - 1]

    expect(model.metrics.map((metric) => metric.label)).toEqual([
      'Agent Runs',
      'Network Runs',
      'Runtime Cost',
      'Agent Run Success',
      'Network Run Success',
      'Average Run Time',
    ])
    expect(averageRunTimeMetric?.comparison?.agent.label).toBe('Agent Run')
    expect(averageRunTimeMetric?.comparison?.network.label).toBe('Network Run')
    expect(model.narrative).toContain('12 Agent Runs')
    expect(model.narrative).toContain('2 Network Runs')
    expect(model.series).toHaveLength(2)
    expect(model.changes).toHaveLength(2)
    expect(model.changes.map((change) => change.resourceLabel)).toContain('Agent')
    expect(model.changes.map((change) => change.resourceLabel)).toContain('Network')
    expect(model.runs.map((run) => run.typeLabel)).toContain('Agent Run')
    expect(model.runs.map((run) => run.typeLabel)).toContain('Network Run')
    expect(model.runs).toHaveLength(2)
    expect(model.environmentTotal).toBe(3)
    expect(model.isExecutionEmpty).toBe(false)
  })

  it('keeps success and error rates separate for Agent and Network Runs', () => {
    const model = adaptProjectOverview(cloneFixture())

    expect(model.reliability.agent.successRate).toBe(91.67)
    expect(model.reliability.agent.errorRate).toBe(8.33)
    expect(model.reliability.network.successRate).toBe(100)
    expect(model.reliability.network.errorRate).toBe(0)
    expect(model.issues.hasIssues).toBe(true)
    expect(model.issues.totalAgentErrors).toBe(1)
    expect(model.issues.totalNetworkErrors).toBe(0)
  })

  it('does not coerce unknown Run values to zero', () => {
    const fixture = cloneFixture()
    fixture.summary.avg_agent_run_duration_ms = null
    fixture.summary.agent_run_success_rate = null
    fixture.summary.agent_run_cost_usd = null
    fixture.summary.unknown_agent_run_cost_count = 2
    fixture.recent_traces[0]!.latency_ms = null
    fixture.recent_traces[0]!.cost_usd = null
    fixture.recent_traces[0]!.cost_known = false
    fixture.recent_network_runs[0]!.cost_usd = null
    fixture.recent_network_runs[0]!.cost_known = false
    fixture.recent_network_runs[0]!.priced_agent_runs = 0
    fixture.recent_network_runs[0]!.unknown_cost_count = 2

    const model = adaptProjectOverview(fixture)
    const agentRun = model.runs.find((run) => run.kind === 'agent')
    const networkRun = model.runs.find((run) => run.kind === 'network')

    expect(formatLatency(null)).toBe('—')
    expect(formatPercent(null)).toBe('—')
    expect(formatCost(null)).toBe('Unknown')
    expect(model.metrics.find((metric) => metric.label === 'Runtime Cost')?.value).toBe('Unknown')
    expect(agentRun?.durationLabel).toBe('—')
    expect(agentRun?.costLabel).toBe('Unknown')
    expect(networkRun?.costLabel).toBe('Unknown')
    expect(networkRun?.costDetail).toBe('Cost unavailable')
  })

  it('preserves legitimate zero values and empty-state semantics', () => {
    const fixture = cloneFixture()
    fixture.summary.agent_runs = 0
    fixture.summary.network_runs = 0
    fixture.summary.terminal_agent_runs = 0
    fixture.summary.terminal_network_runs = 0
    fixture.summary.avg_agent_run_duration_ms = 0
    fixture.summary.agent_run_success_rate = null
    fixture.summary.network_run_success_rate = null
    fixture.summary.agent_run_cost_usd = 0
    fixture.timeseries = []
    fixture.capabilities.sessions_jobs = true

    const model = adaptProjectOverview(fixture)

    expect(formatLatency(0)).toContain('0')
    expect(formatPercent(0)).toBe('0%')
    expect(formatCost(0)).not.toBe('Unknown')
    expect(model.narrative).toContain('no Agent Runs or Network Runs')
    expect(model.isExecutionEmpty).toBe(true)
    expect(model.capabilities.sessions_jobs).toBe(true)
  })

  it('shows a partial Network Run cost without hiding the known subtotal', () => {
    const fixture = cloneFixture()
    fixture.recent_network_runs[0]!.cost_usd = 0.04
    fixture.recent_network_runs[0]!.cost_known = false
    fixture.recent_network_runs[0]!.priced_agent_runs = 1
    fixture.recent_network_runs[0]!.total_agent_runs = 2
    fixture.recent_network_runs[0]!.unknown_cost_count = 1

    const model = adaptProjectOverview(fixture)
    const networkRun = model.runs.find((run) => run.kind === 'network')

    expect(networkRun?.costLabel).not.toBe('Unknown')
    expect(networkRun?.costDetail).toContain('Partial')
    expect(networkRun?.costDetail).toContain('1/2')
  })

  it('marks an unfinished Network cost as a current subtotal', () => {
    const fixture = cloneFixture()
    Object.assign(fixture.recent_network_runs[0]!, { cost_usd: 0.1, cost_known: false,
      status: 'running', total_agent_runs: 1, priced_agent_runs: 1, unknown_cost_count: 0 })
    const row = adaptProjectOverview(fixture).runs.find((run) => run.kind === 'network')
    expect(row?.costDetail).toBe('Current subtotal · Network Run not finalized')
    expect(row?.costLabel).not.toBe('Unknown')
  })

  it('distinguishes mutable Draft changes from immutable releases', () => {
    const fixture = cloneFixture()
    fixture.recent_changes = [
      {
        id: '88888888-8888-8888-8888-888888888888',
        resource_type: 'network',
        resource_id: '66666666-6666-6666-6666-666666666666',
        resource_name: 'Support Network',
        environment: 'draft',
        action: 'draft_updated',
        version: null,
        revision: 14,
        description: null,
        occurred_at: '2026-06-20T11:30:00Z',
        immutable: false,
      },
    ]

    const model = adaptProjectOverview(fixture)

    expect(model.changes[0]?.actionLabel).toBe('Draft updated')
    expect(model.changes[0]?.versionLabel).toBe('Draft revision 14')
    expect(model.changes[0]?.immutable).toBe(false)
  })
})
