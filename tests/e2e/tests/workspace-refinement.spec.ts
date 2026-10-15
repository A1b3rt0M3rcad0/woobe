import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { login } from '../fixtures/control-plane'
import { installWorkspaceRefinement, longNodeName, networkPath, playgroundPath } from '../fixtures/workspace-refinement'

const viewports = [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }, { width: 1366, height: 768 }, { width: 1024, height: 768 }]

for (const theme of ['light', 'dark'] as const) for (const viewport of viewports) test(`workspace reading at ${viewport.width}px in ${theme}`, async ({ page }) => {
  await page.setViewportSize(viewport)
  await installWorkspaceRefinement(page)
  await login(page)
  await page.goto(playgroundPath)
  await page.getByLabel('Theme', { exact: true }).selectOption(theme)
  await page.getByLabel('Message', { exact: true }).fill('Keep this unsent message.')
  await page.getByRole('button', { name: 'Runs', exact: true }).click()
  await page.getByRole('button', { name: /Agent Run · success/ }).click()
  const metrics = page.locator('[data-run-metrics]')
  await expect(metrics.getByText('Cost unavailable', { exact: true })).toBeVisible()
  await expect(metrics.getByText('1.69s', { exact: true })).toBeVisible()
  await metrics.getByText('Cost details', { exact: true }).click()
  await expect(metrics.getByText('Status: unknown_pricing')).toBeVisible()
  await expect(page.locator('[data-contribution-bars]').first()).toContainText('Persisted contribution units')
  await expect(page.locator('[data-contribution-bars]').first()).toContainText('0.05%')
  expect(await metrics.evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  await page.getByLabel('Theme', { exact: true }).selectOption(theme === 'dark' ? 'light' : 'dark')
  await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Keep this unsent message.')
  await expect(metrics.locator('details')).toHaveAttribute('open', '')
  await page.getByLabel('Theme', { exact: true }).selectOption(theme)
  if (process.env.WOOBE_CAPTURE_REFINEMENT === '1' && viewport.width === 1440) {
    await page.setViewportSize({ width: 1440, height: 1100 })
    await metrics.getByText('Cost details', { exact: true }).click()
    const dir = resolve(process.cwd(), '../../docs/screenshots/themes')
    await mkdir(dir, { recursive: true })
    await page.screenshot({ path: resolve(dir, `agent-playground-${theme}.png`), animations: 'disabled' })
  }
  await page.goto(networkPath)
  await expect(page.locator('.react-flow__node').first()).toBeVisible()
  await expect(page.getByRole('status', { name: 'Preparing Network Canvas' })).toHaveCount(0)
  const node = page.locator('.react-flow__node').filter({ hasText: longNodeName })
  await expect(node).toContainText(longNodeName)
  await expect(node.locator('article')).toHaveCSS('width', '280px')
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  await page.waitForTimeout(400)
  const transform = await page.locator('.react-flow__viewport').getAttribute('style')
  await page.getByLabel('Theme', { exact: true }).selectOption(theme === 'dark' ? 'light' : 'dark')
  await expect(page.locator('.react-flow__viewport')).toHaveAttribute('style', transform!)
  await page.getByLabel('Theme', { exact: true }).selectOption(theme)
  await page.getByRole('button', { name: 'Hide inspector', exact: true }).click()
  await expect(page.getByRole('complementary', { name: 'Network inspector', exact: true })).toBeHidden()
  await page.getByRole('button', { name: 'Show inspector', exact: true }).click()
  if (process.env.WOOBE_CAPTURE_REFINEMENT === '1' && viewport.width === 1440) {
    await page.getByRole('button', { name: 'Fit Network in the visible Canvas' }).click()
    await page.waitForTimeout(400)
    await page.screenshot({ path: resolve(process.cwd(), `../../docs/screenshots/themes/network-workspace-${theme}.png`), animations: 'disabled' })
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
})

for (const [label, cost, costStatus, units, tokens] of [
  ['small cost and balanced composition', .00000004, 'known', [50, 50], 123456789],
  ['zero cost and zero contribution', 0, 'known', [0], 0],
  ['partial cost and one category', .0003, 'partial', [100], 100],
  ['missing composition', null, 'unknown_pricing', [], 152],
] as const) test(label, async ({ page }) => {
  await installWorkspaceRefinement(page, { cost, costStatus, units: [...units], tokens })
  await login(page); await page.goto(playgroundPath)
  await page.getByRole('button', { name: 'Runs', exact: true }).click()
  await page.getByRole('button', { name: /Agent Run · success/ }).click()
  const metrics = page.locator('[data-run-metrics]')
  if (cost === .00000004) await expect(metrics.getByText('$0.00000004', { exact: true })).toBeVisible()
  if (cost === 0) await expect(metrics.getByText('$0.0000', { exact: true })).toBeVisible()
  if (costStatus === 'partial') await expect(metrics.getByText('$0.0003+', { exact: true })).toBeVisible()
  if (units.length) {
    const bars = page.locator('[data-contribution-bars]').first().locator('dl > div > div[aria-hidden] > div')
    const expected = units.map(v => `${units.reduce((a, b) => a + b, 0) ? v / units.reduce((a, b) => a + b, 0) * 100 : 0}%`)
    expect(await bars.evaluateAll(els => els.map(el => (el as HTMLElement).style.width))).toEqual(units.every(value => value === 0) ? [] : expected)
  } else await expect(page.getByText('No source-level Context composition was persisted for this Run.')).toBeVisible()
})

test('larger Network retains keyboard selection, unsaved labels and viewport across themes', async ({ page }) => {
  await installWorkspaceRefinement(page, { nodes: 14 })
  await login(page); await page.goto(networkPath)
  await expect(page.locator('.react-flow__node')).toHaveCount(14)
  await expect(page.getByRole('status', { name: 'Preparing Network Canvas' })).toHaveCount(0)
  const entry = page.locator('.react-flow__node[data-id="node-0"]')
  await entry.focus(); await entry.press('Enter')
  const label = page.getByLabel('Node label', { exact: true })
  await expect(label).toHaveValue(longNodeName)
  await label.fill('Unsaved readable entry label')
  await page.getByLabel('Theme', { exact: true }).selectOption('dark')
  await expect(label).toHaveValue('Unsaved readable entry label')
  await expect(entry).toHaveClass(/selected/)
  await page.getByRole('button', { name: 'Hide inspector', exact: true }).click()
  await page.getByRole('button', { name: 'Show inspector', exact: true }).click()
  await expect(label).toHaveValue('Unsaved readable entry label')
})
