import { expect, test, type Locator, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { installApi, login, respond, workspace, project } from '../fixtures/control-plane'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

const root = `/workspaces/${workspace.id}/projects/${project.id}`

async function renderedFont(page: Page, locator: Locator, role: string, expected: 'Inter' | 'JetBrains Mono' | 'serif') {
  const probe = `type-${role}`
  await locator.first().evaluate((element, id) => element.setAttribute('data-type-probe', id), probe)
  const computed = await locator.first().evaluate(element => {
    const style = getComputedStyle(element)
    return { family: style.fontFamily, weight: style.fontWeight, size: style.fontSize, lineHeight: style.lineHeight }
  })
  const client = await page.context().newCDPSession(page)
  await client.send('DOM.enable')
  await client.send('CSS.enable')
  const { root: document } = await client.send('DOM.getDocument')
  const { nodeId } = await client.send('DOM.querySelector', { nodeId: document.nodeId, selector: `[data-type-probe="${probe}"]` })
  const { fonts } = await client.send('CSS.getPlatformFontsForNode', { nodeId })
  await client.detach()
  const used = fonts.filter(font => font.glyphCount > 0)
  expect(used.length, `${role}: ${JSON.stringify(fonts)}`).toBeGreaterThan(0)
  if (expected === 'serif') {
    expect(computed.family).toContain('Georgia')
    expect(computed.weight).toBe('400')
    // Georgia is a system preference, not a bundled webfont. Record the actual fallback.
    expect(used.every(font => !['Inter', 'JetBrains Mono'].includes(font.familyName))).toBeTruthy()
    if (process.env.WOOBE_REQUIRE_GEORGIA === '1') expect(used.some(font => font.familyName === 'Georgia' && !font.isCustomFont), `${role}: ${JSON.stringify(fonts)}`).toBeTruthy()
  } else {
    expect(used.some(font => font.familyName === expected && font.isCustomFont), `${role}: ${JSON.stringify(fonts)}`).toBeTruthy()
  }
  return { role, expected, computed, fonts }
}

for (const width of [1440, 768, 390]) test(`editorial, interface and technical fonts render separately at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1100 })
  await page.clock.setFixedTime(new Date('2026-06-20T12:00:00Z'))
  await installApi(page, { asacAgent: true })
  await page.route('**/core/projects/project-a/overview*', route => respond(route, projectOverviewFixture))
  await login(page)
  await page.goto(root)
  await expect(page.getByRole('heading', { name: 'Run Activity', exact: true })).toBeVisible()
  await page.evaluate(async () => { await document.fonts.ready })
  const evidence = []
  for (const [role, locator, family] of [
    ['page-title', page.getByRole('heading', { name: 'Project Overview', exact: true }), 'serif'],
    ['overview-section', page.getByRole('heading', { name: 'What happened', exact: true }), 'serif'],
    ['description', page.getByText('Volume, reliability, performance, and cost in the selected period.', { exact: true }), 'Inter'],
    ['breadcrumb', page.locator('header').getByRole('link', { name: workspace.name, exact: true }), 'Inter'],
    ['refresh', page.getByRole('button', { name: 'Refresh', exact: true }), 'Inter'],
    ['range', page.getByLabel('Dashboard range'), 'Inter'],
    ['analysis-panel', page.getByRole('heading', { name: 'Run Activity', exact: true }), 'Inter'],
    ['metric', page.getByText('$0.25', { exact: true }), 'JetBrains Mono'],
  ] as const) evidence.push(await renderedFont(page, locator, role, family))
  if (width < 1024) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  evidence.push(await renderedFont(page, page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Overview', exact: true }), 'navigation', 'Inter'))
  if (width < 1024) await page.keyboard.press('Escape')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  if (process.env.WOOBE_CAPTURE_DOCS === '1') {
    const directory = resolve(process.cwd(), '../../docs/design/fonts')
    await mkdir(directory, { recursive: true })
    await writeFile(resolve(directory, `typography-${width}px.json`), JSON.stringify({ browser: page.context().browser()?.version(), viewport: { width, height: 1100 }, evidence }, null, 2) + '\n')
  }
})

test('authentication uses editorial serif titles and Inter form controls', async ({ page }) => {
  await installApi(page)
  await page.goto('/login')
  await page.evaluate(async () => { await document.fonts.ready })
  const evidence = []
  evidence.push(await renderedFont(page, page.getByRole('heading', { name: 'Sign in to Woobe' }), 'sign-in-title', 'serif'))
  evidence.push(await renderedFont(page, page.getByRole('heading', { name: 'From a first draft to production.' }), 'product-headline', 'serif'))
  await page.getByLabel('Email', { exact: true }).fill('owner@example.test')
  evidence.push(await renderedFont(page, page.getByLabel('Email', { exact: true }), 'email', 'Inter'))
  evidence.push(await renderedFont(page, page.getByRole('button', { name: 'Sign in', exact: true }), 'sign-in-action', 'Inter'))
  if (process.env.WOOBE_CAPTURE_DOCS === '1') await writeFile(resolve(process.cwd(), '../../docs/design/fonts/typography-auth.json'), JSON.stringify({ browser: page.context().browser()?.version(), evidence }, null, 2) + '\n')
})
