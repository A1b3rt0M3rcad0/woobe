import { expect, test, type Locator } from '@playwright/test'
import { installApi, login, workspace } from '../fixtures/control-plane'

async function visibleLockup(logo: Locator, variant: 'primary' | 'orange-white') {
  await expect(logo).toBeVisible()
  const artwork = logo.locator('img:visible')
  await expect(artwork).toHaveCount(1)
  await expect(artwork).toHaveAttribute('src', new RegExp(`woobe-lockup-${variant}`))
  await expect.poll(() => artwork.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBe(471)
  const dimensions = await artwork.boundingBox()
  expect(dimensions!.width / dimensions!.height).toBeCloseTo(471 / 102, 1)
}

for (const theme of ['light', 'dark'] as const) for (const width of [1440, 390]) test(`brand artwork is legible and loaded at ${width}px in ${theme}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1100 })
  await page.emulateMedia({ colorScheme: theme })
  await installApi(page)
  await page.goto('/login')
  await visibleLockup(page.getByRole('img', { name: 'Woobe', exact: true }), theme === 'dark' ? 'orange-white' : 'primary')
  await page.screenshot({ path: test.info().outputPath(`brand-login-${theme}-${width}.png`), animations: 'disabled' })
  await login(page)
  if (width < 1024) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await visibleLockup(page.getByRole('img', { name: 'Woobe', exact: true }), 'orange-white')
  if (width < 1024) await page.keyboard.press('Escape')
  await page.goto(`/workspaces/${workspace.id}/projects`)
  if (width < 1024) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await visibleLockup(page.getByRole('img', { name: 'Woobe', exact: true }), 'orange-white')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  await page.screenshot({ path: test.info().outputPath(`brand-navigation-${theme}-${width}.png`), animations: 'disabled' })
})

test('browser brand assets are real images with transparent backgrounds', async ({ page }) => {
  await page.goto('/login')
  const svg = await page.request.get('/favicon.svg')
  expect(svg.headers()['content-type']).toContain('image/svg+xml')
  expect(await svg.text()).toContain('Woobe orange modular mark')
  const assets = await page.evaluate(async () => {
    const manifest = await (await fetch('/site.webmanifest')).json()
    const images = await Promise.all([
      ['/favicon-16.png', 16], ['/favicon-32.png', 32], ['/apple-touch-icon.png', 180], ['/icon-192.png', 192], ['/icon-512.png', 512],
    ].map(async ([path, size]) => {
      const bitmap = await createImageBitmap(await (await fetch(String(path))).blob())
      const canvas = document.createElement('canvas')
      canvas.width = bitmap.width; canvas.height = bitmap.height
      const context = canvas.getContext('2d')!
      context.drawImage(bitmap, 0, 0)
      const cornerAlpha = context.getImageData(0, 0, 1, 1).data[3]
      const result = { width: bitmap.width, height: bitmap.height, size, cornerAlpha }
      bitmap.close()
      return result
    }))
    return { manifest, images }
  })
  expect(assets.manifest.name).toBe('Woobe Control Plane')
  for (const image of assets.images) {
    expect(image.width).toBe(image.size)
    expect(image.height).toBe(image.size)
    expect(image.cornerAlpha).toBe(0)
  }
})
