import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { installApi, login, respond, workspace, project } from '../fixtures/control-plane'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

const root = `/workspaces/${workspace.id}/projects/${project.id}`
async function openOverview(page: Page) {
  await installApi(page, { asacAgent: true })
  await page.route('**/core/projects/project-a/overview*', route => respond(route, projectOverviewFixture))
  await login(page)
  await page.goto(root)
  await expect(page.getByRole('heading', { name: 'Run Activity', exact: true })).toBeVisible()
}

for (const width of [1440, 1280, 768, 390, 320]) test(`overview hierarchy and accessibility at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 1100 })
  await openOverview(page)
  await expect(page.getByRole('button', { name: 'Agent Runs', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Network Runs', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Agent Run Success', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Runtime Cost', exact: true })).toBeVisible()
  await expect(page.getByText('11 / 12 terminal Runs successful', { exact: true }).first()).toBeVisible()
  const errors = await page.getByRole('heading', { name: 'Execution errors', exact: true }).boundingBox()
  const chart = await page.getByRole('heading', { name: 'Run Activity', exact: true }).boundingBox()
  expect(errors!.y).toBeLessThan(chart!.y)
  if (width === 1440) expect(chart!.y).toBeLessThan(650)
  // Include internal scrollers: a fixed shell can conceal horizontal overflow.
  expect(await page.locator('#main-content').evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
  for (const heading of ['Run Activity', 'Recent Runs', 'Current Project State']) {
    await page.getByRole('heading', { name: heading, exact: true }).scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath(`${heading.replaceAll(' ', '-').toLowerCase()}.png`), animations: 'disabled' })
  }
})

test('activity uses real time positions and exposes sparse intervals by keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 })
  await openOverview(page)
  const chart = page.getByRole('img', { name: 'Agent Runs, Network Runs and Errors by time bucket' })
  const bars = chart.locator('[data-series="agent"]')
  const viewWidth = Number((await chart.getAttribute('viewBox'))!.split(' ')[2])
  expect(Number(await bars.first().getAttribute('x'))).toBeGreaterThan(viewWidth * 0.85)
  await expect(page.getByText('2 of 24 hourly buckets reported. Gaps are unavailable, not zero activity.')).toBeVisible()
  const interval = page.getByLabel('Activity interval', { exact: true })
  await expect(interval.locator('option')).toHaveCount(24)
  await interval.focus()
  await page.keyboard.press('Home')
  await page.keyboard.press('Enter')
  await expect(interval).toHaveValue('0')
  await expect(page.getByText('No data was returned for this interval. Period totals are shown above.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Previous activity interval' })).toBeDisabled()
  await interval.selectOption('22')
  await page.getByRole('button', { name: 'Next activity interval' }).click()
  await expect(interval).toHaveValue('23')
  await expect(page.getByRole('button', { name: 'Next activity interval' })).toBeDisabled()
  await expect(page.getByLabel('Selected interval details')).toContainText('$0.15')
  const analysis = page.getByLabel('Run activity analysis', { exact: true })
  for (const [series, label] of [['agent', 'Agent Runs'], ['network', 'Network Runs'], ['errors', 'Errors (subset)']]) {
    const marker = analysis.getByText(label, { exact: true }).first().locator('span')
    const legend = await marker.evaluate(el => getComputedStyle(el).color)
    expect(await chart.locator(`[data-series="${series}"]`).first().evaluate(el => getComputedStyle(el).color)).toBe(legend)
  }
  await page.getByRole('button', { name: 'Open Run ledger', exact: true }).click()
  await expect(page).toHaveURL(`${root}/traces`)
})

test('a new environment never displays totals from the previous filter', async ({ page }) => {
  await openOverview(page)
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  let requested = false
  await page.route('**/core/projects/project-a/overview*', async route => {
    const params = new URL(route.request().url()).searchParams
    expect(params.get('environment')).toBe('production')
    expect(params.get('bucket')).toBe('hour')
    requested = true
    await pending
    await respond(route, null, 500)
  })
  await page.getByRole('button', { name: 'Production', exact: true }).click()
  await expect.poll(() => requested).toBe(true)
  await expect(page.getByLabel('Loading project overview')).toBeVisible()
  await expect(page.getByText('$0.25', { exact: true })).toHaveCount(0)
  release()
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('$0.25', { exact: true })).toHaveCount(0)
})

test('failed refresh keeps same-filter data with an explicit warning', async ({ page }) => {
  await openOverview(page)
  await page.route('**/core/projects/project-a/overview*', route => respond(route, null, 500))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByText('The latest refresh failed. Showing the last available Overview data.')).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('$0.25', { exact: true })).toBeVisible()
})

test('reported zero activity and partially priced cost stay distinct from gaps', async ({ page }) => {
  await openOverview(page)
  const fixture = structuredClone(projectOverviewFixture)
  Object.assign(fixture.timeseries[0], { agent_runs: 0, network_runs: 0, agent_run_success: 0,
    network_run_success: 0, cost_usd: 0, avg_agent_run_duration_ms: null, avg_network_run_duration_ms: null })
  fixture.timeseries[1].unknown_cost_count = 1
  await page.route('**/core/projects/project-a/overview*', route => respond(route, fixture))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  const detail = page.getByLabel('Selected interval details')
  await expect(detail).toContainText('1 Runs unpriced · Partial')
  await expect(detail).toContainText('$0.15')
  await page.getByLabel('Activity interval', { exact: true }).selectOption('22')
  await expect(detail).toContainText('$0.00')
  await expect(detail.getByText('0', { exact: true })).toHaveCount(3)
  await expect(detail).not.toContainText('No data was returned')
  await page.getByLabel('Activity interval', { exact: true }).selectOption('21')
  await expect(detail).toContainText('No data was returned')
  await expect(detail).not.toContainText('$0.00')
})

test('the seven-day filter preserves the requested time domain and daily buckets', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-06-20T12:00:00Z'))
  await openOverview(page)
  await page.route('**/core/projects/project-a/overview*', async route => {
    const params = new URL(route.request().url()).searchParams
    expect(params.get('from')).toBe('2026-06-13T12:00:00.000Z')
    expect(params.get('to')).toBe('2026-06-20T12:00:00.000Z')
    expect(params.get('bucket')).toBe('day')
    const fixture = structuredClone(projectOverviewFixture)
    Object.assign(fixture, { from: params.get('from'), to: params.get('to'), bucket: 'day' })
    fixture.timeseries[0].bucket_start = '2026-06-19T00:00:00Z'
    fixture.timeseries[1].bucket_start = '2026-06-20T00:00:00Z'
    await respond(route, fixture)
  })
  await page.getByLabel('Dashboard range').selectOption('7d')
  await expect(page.getByText('2 of 8 daily buckets reported. Gaps are unavailable, not zero activity.')).toBeVisible()
  await expect(page.getByLabel('Activity interval', { exact: true }).locator('option')).toHaveCount(8)
  await expect(page.getByText('$0.25', { exact: true })).toBeVisible()
})
