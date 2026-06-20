import { describe, expect, it } from 'vitest'
import { adaptProjectOverview, formatCost, formatLatency, formatPercent } from './adapters'
import { projectOverviewFixture } from './fixtures'

function cloneFixture() {
  return structuredClone(projectOverviewFixture)
}

describe('adaptProjectOverview', () => {
  it('maps the overview contract to the dashboard view model', () => {
    const model = adaptProjectOverview(cloneFixture())

    expect(model.metrics.map((metric) => metric.label)).toEqual([
      'Active Agents',
      'Production Agents',
      'Runtime Requests',
      'Avg Latency',
      'Success Rate',
      'Estimated Cost',
    ])
    expect(model.series).toHaveLength(2)
    expect(model.releases[0]?.environmentLabel).toBe('Production')
    expect(model.traces[0]?.statusLabel).toBe('Success')
    expect(model.environmentTotal).toBe(3)
    expect(model.isExecutionEmpty).toBe(false)
  })

  it('does not coerce null values to zero', () => {
    const fixture = cloneFixture()
    fixture.summary.avg_latency_ms = null
    fixture.summary.success_rate = null
    fixture.summary.cost_usd = null
    fixture.summary.unknown_cost_count = 2
    fixture.recent_traces[0]!.latency_ms = null
    fixture.recent_traces[0]!.total_tokens = null
    fixture.recent_traces[0]!.cost_usd = null
    fixture.recent_traces[0]!.cost_known = false

    const model = adaptProjectOverview(fixture)

    expect(formatLatency(null)).toBe('—')
    expect(formatPercent(null)).toBe('—')
    expect(formatCost(null)).toBe('Unknown')
    expect(model.metrics.find((metric) => metric.label === 'Estimated Cost')?.value).toBe('Unknown')
    expect(model.traces[0]?.latencyLabel).toBe('—')
    expect(model.traces[0]?.tokenLabel).toBe('—')
    expect(model.traces[0]?.costLabel).toBe('Unknown')
  })

  it('preserves legitimate zero values and capability flags', () => {
    const fixture = cloneFixture()
    fixture.summary.requests = 0
    fixture.summary.avg_latency_ms = 0
    fixture.summary.success_rate = 0
    fixture.summary.cost_usd = 0
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
