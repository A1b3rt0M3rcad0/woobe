import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { installApi, login, project, respond, workspace } from '../fixtures/control-plane'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

function luminance(color: string) {
  const values = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {
    const channel = value / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722
}
function contrast(first: string, second: string) {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}
async function colors(locator: Locator) {
  return locator.evaluate(element => {
    const style = getComputedStyle(element)
    return { background: style.backgroundColor, text: style.color, outline: style.outlineColor, outlineStyle: style.outlineStyle }
  })
}
async function navigation(page: Page, width: number, label: string) {
  if (width < 1024) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await expect(page.getByRole('navigation', { name: label })).toBeVisible()
  return page.locator('aside.woobe-navigation:visible')
}

for (const theme of ['light', 'dark'] as const) for (const width of [1440, 390]) test(`navigation and account settings follow the ${theme} palette at ${width}px`, async ({ page }) => {
  await page.emulateMedia({ colorScheme: theme })
  await page.setViewportSize({ width, height: 1100 })
  await installApi(page, { asacAgent: true })
  await page.route('**/core/projects/project-a/overview*', route => respond(route, projectOverviewFixture))
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects`)
  const workspaceNav = await navigation(page, width, 'Workspace navigation')
  const workspaceColors = await colors(workspaceNav)
  expect(luminance(workspaceColors.background)).toBeLessThan(0.06)
  if (theme === 'dark') {
    const canvas = await page.evaluate(() => {
      const probe = document.createElement('span')
      probe.style.backgroundColor = 'rgb(var(--woobe-canvas))'
      document.body.appendChild(probe)
      const color = getComputedStyle(probe).backgroundColor
      probe.remove()
      return color
    })
    expect(workspaceColors.background).toBe(canvas)
  }
  if (width < 1024) await page.keyboard.press('Escape')

  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}`)
  const projectNav = await navigation(page, width, 'Project navigation')
  expect((await colors(projectNav)).background).toBe(workspaceColors.background)
  const overview = projectNav.getByRole('link', { name: 'Overview', exact: true })
  await expect(overview).toHaveAttribute('aria-current', 'page')
  const activeColors = await colors(overview)
  expect(contrast(activeColors.text, activeColors.background)).toBeGreaterThanOrEqual(4.5)

  await projectNav.getByRole('button', { name: 'Open account settings', exact: true }).click()
  const account = page.getByRole('dialog', { name: 'Account settings', exact: true })
  await expect(account).toBeVisible()
  const accountLuminance = luminance((await colors(account)).background)
  if (theme === 'light') expect(accountLuminance).toBeGreaterThan(0.85)
  else expect(accountLuminance).toBeLessThan(0.06)
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
  await page.keyboard.press('Escape')
  await expect(account).not.toBeVisible()
  const accountTrigger = projectNav.getByRole('button', { name: 'Open account settings', exact: true })
  await expect(accountTrigger).toBeFocused()
  expect(contrast((await colors(accountTrigger)).outline, workspaceColors.background)).toBeGreaterThanOrEqual(3)
  await overview.focus()
  const focusedColors = await colors(overview)
  expect(focusedColors.outlineStyle).toBe('solid')
  expect(contrast(focusedColors.outline, focusedColors.background)).toBeGreaterThanOrEqual(3)
})
