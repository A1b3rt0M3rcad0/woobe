import { expect, test } from '@playwright/test'
import { installApi, login } from '../fixtures/control-plane'

for (const width of [1440, 390]) test(`theme control is available only in account settings at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1100 })
  await installApi(page)
  for (const path of ['/register', '/login']) {
    await page.goto(path)
    await expect(page.getByLabel('Theme', { exact: true })).toHaveCount(0)
  }
  await login(page)
  await expect(page.getByLabel('Theme', { exact: true })).toHaveCount(0)
  if (width < 1024) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await page.getByRole('button', { name: 'Open account settings', exact: true }).click()
  const modal = page.getByRole('dialog', { name: 'Account settings', exact: true })
  await expect(modal).toBeVisible()
  await modal.getByLabel('Theme', { exact: true }).selectOption('dark')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.keyboard.press('Escape')
  await expect(modal).toBeHidden()
  await expect(page.getByRole('button', { name: 'Open account settings', exact: true })).toBeFocused()
  await expect(page.getByLabel('Theme', { exact: true })).toHaveCount(0)
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

for (const system of ['light', 'dark'] as const) test(`System follows ${system} and explicit preferences survive reload`, async ({ page }) => {
  await page.emulateMedia({ colorScheme: system })
  await installApi(page)
  await page.goto('/settings')
  const select = page.getByRole('combobox', { name: 'Theme', exact: true })
  await expect(select).toHaveValue('system')
  await expect(page.locator('html')).toHaveAttribute('data-theme', system)
  await page.emulateMedia({ colorScheme: system === 'dark' ? 'light' : 'dark' })
  await expect(page.locator('html')).toHaveAttribute('data-theme', system === 'dark' ? 'light' : 'dark')
  for (const choice of ['light', 'dark'] as const) {
    await select.selectOption(choice)
    await select.focus()
    await page.emulateMedia({ colorScheme: choice === 'dark' ? 'light' : 'dark' })
    await expect(page.locator('html')).toHaveAttribute('data-theme', choice)
    await expect(select).toBeFocused()
    await expect(page.getByRole('dialog', { name: 'Account settings', exact: true })).toBeVisible()
    await page.reload()
    await expect(select).toHaveValue(choice)
    await expect(page.locator('html')).toHaveAttribute('data-theme', choice)
  }
  await select.selectOption('system')
  expect(await page.evaluate(() => localStorage.getItem('woobe.theme'))).toBe('system')
})

test('invalid storage and denied storage fall back safely', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.emulateMedia({ colorScheme: 'dark' })
  await installApi(page)
  await page.addInitScript(() => {
    try { localStorage.setItem('woobe.theme', 'invalid') } catch { /* Storage may be blocked on reload. */ }
  })
  await page.goto('/settings')
  await expect(page.getByLabel('Theme', { exact: true })).toHaveValue('system')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.addInitScript(() => Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Storage blocked', 'SecurityError') } }))
  await page.reload()
  await page.getByLabel('Theme', { exact: true }).selectOption('light')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByRole('dialog', { name: 'Account settings', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Theme', { exact: true })).toHaveValue('system')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(pageErrors).toEqual([])
})

test('theme preference synchronizes between tabs, including cleared storage', async ({ page, context }) => {
  await installApi(page)
  await page.goto('/settings')
  const second = await context.newPage()
  await installApi(second)
  await second.goto('/settings')
  await page.getByLabel('Theme', { exact: true }).selectOption('dark')
  await expect(second.getByLabel('Theme', { exact: true })).toHaveValue('dark')
  await expect(second.locator('html')).toHaveAttribute('data-theme', 'dark')
  await second.evaluate(() => localStorage.clear())
  await expect(page.getByLabel('Theme', { exact: true })).toHaveValue('system')
  await second.close()
})

for (const theme of ['light', 'dark'] as const) test(`${theme} semantic text and control contrast`, async ({ page }) => {
  await installApi(page); await page.goto('/settings')
  await page.getByLabel('Theme', { exact: true }).selectOption(theme)
  const results = await page.evaluate(() => {
    const color = (token: string) => {
      const probe = document.createElement('span')
      probe.style.color = `rgb(var(--woobe-${token}))`
      document.body.appendChild(probe)
      const rgb = getComputedStyle(probe).color.match(/[\d.]+/g)!.slice(0, 3).map(Number)
      probe.remove()
      const channels = rgb.map(c => { c /= 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4 })
      return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722
    }
    const contrast = (a: string, b: string) => (Math.max(color(a), color(b)) + .05) / (Math.min(color(a), color(b)) + .05)
    return [
      ...['surface', 'workspace', 'elevated', 'control', 'selected'].flatMap(bg => ['ink', 'muted', 'link', 'success', 'warning', 'error', 'info', 'network'].map(ink => ({ pair: `${ink}/${bg}`, actual: contrast(ink, bg), minimum: 4.5 }))),
      ...['surface', 'workspace', 'control'].map(bg => ({ pair: `control-border/${bg}`, actual: contrast('control-border', bg), minimum: 3 })),
      { pair: 'on-primary/primary', actual: contrast('on-primary', 'primary'), minimum: 4.5 },
    ]
  })
  for (const { pair, actual, minimum } of results) expect(actual, `${theme}: ${pair}`).toBeGreaterThanOrEqual(minimum)
})
