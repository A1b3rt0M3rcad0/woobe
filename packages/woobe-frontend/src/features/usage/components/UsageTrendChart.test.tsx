import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { UsageTrendChart } from './UsageTrendChart'
import type { ProjectUsageTimeseriesPoint } from '../types'

function makePoint(overrides: Partial<ProjectUsageTimeseriesPoint> = {}): ProjectUsageTimeseriesPoint {
  return {
    bucket_start: '2026-08-13T00:00:00Z',
    agent_runs: 1,
    direct_agent_runs: 1,
    network_agent_runs: 0,
    successful_agent_runs: 1,
    failed_agent_runs: 0,
    network_runs: 0,
    successful_network_runs: 0,
    failed_network_runs: 0,
    known_cost_usd: 0,
    network_run_cost_usd: 0,
    agent_cost_per_run: 0,
    network_cost_per_run: 0,
    llm_calls: 1,
    input_tokens: 0,
    output_tokens: 0,
    priced_agent_runs: 1,
    partial_cost_agent_runs: 0,
    unpriced_agent_runs: 0,
    runtime_requests: 1,
    successful_requests: 1,
    failed_requests: 0,
    priced_requests: 1,
    partial_cost_requests: 0,
    unpriced_requests: 0,
    ...overrides,
  }
}

function chartMarkup(point: ProjectUsageTimeseriesPoint, mode: 'cost' | 'runs' | 'unit_cost' | 'tokens') {
  return renderToStaticMarkup(
    <UsageTrendChart
      points={[point]}
      mode={mode}
      bucket="day"
      contextLabel="Last 30 days · All environments · All operations · By Agent ·"
      onModeChange={() => undefined}
    />,
  )
}

function numericAttribute(tag: string, attribute: string) {
  const match = tag.match(new RegExp(`${attribute}="([^"]+)"`))
  if (!match) throw new Error(`Missing ${attribute} in ${tag}`)
  return Number(match[1])
}

function primaryPointTag(markup: string) {
  const match = markup.match(/<circle[^>]*class="[^"]*fill-primary-light[^"]*"[^>]*>/)
  if (!match) throw new Error('Primary point not found')
  return match[0]
}

function secondaryBarTag(markup: string) {
  const match = markup.match(/<rect[^>]*class="fill-violet-400\/65"[^>]*>/)
  if (!match) throw new Error('Secondary bar not found')
  return match[0]
}

describe('UsageTrendChart adaptive scaling', () => {
  it('keeps very small cost series visible without a fixed one-dollar domain', () => {
    const markup = chartMarkup(makePoint({
      known_cost_usd: 0.0201,
      network_run_cost_usd: 0.000072,
      agent_cost_per_run: 0.0201,
      network_cost_per_run: 0.000072,
      network_runs: 1,
      successful_network_runs: 1,
    }), 'cost')

    expect(numericAttribute(primaryPointTag(markup), 'cy')).toBeLessThan(60)
    expect(numericAttribute(secondaryBarTag(markup), 'height')).toBeGreaterThan(150)
    expect(markup).toContain('Series use independent relative scales; cards show absolute values.')
  })

  it('keeps low-volume Network Runs visible next to much larger Agent Run volume', () => {
    const markup = chartMarkup(makePoint({
      agent_runs: 10_000,
      successful_agent_runs: 10_000,
      runtime_requests: 10_000,
      successful_requests: 10_000,
      network_runs: 2,
      successful_network_runs: 2,
    }), 'runs')

    expect(numericAttribute(primaryPointTag(markup), 'cy')).toBeLessThan(60)
    expect(numericAttribute(secondaryBarTag(markup), 'height')).toBeGreaterThan(150)
  })

  it('keeps all-zero values on the baseline without inventing visible magnitude', () => {
    const markup = chartMarkup(makePoint(), 'cost')

    expect(numericAttribute(primaryPointTag(markup), 'cy')).toBe(202)
    expect(markup).not.toContain('fill-violet-400/65')
  })
})
