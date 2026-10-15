import { chromium, expect, test } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { installWorkspaceRefinement, networkPath, playgroundPath } from '../fixtures/workspace-refinement'
import { login } from '../fixtures/control-plane'

for (const factor of [1.25, 1.5, 2]) test(`workspaces remain operable at native browser zoom ${factor * 100}%`, async ({}, info) => {
  // Chromium's persisted default zoom is a logarithmic zoom level. The default
  // partition key is "x" (empty relative partition path), in Chromium 136+.
  // This exercises browser zoom, without scaling application CSS or installing extensions.
  const profile = info.outputPath('browser-profile')
  await mkdir(`${profile}/Default`, { recursive: true })
  await writeFile(`${profile}/Default/Preferences`, JSON.stringify({ partition: { default_zoom_level: { x: Math.log(factor) / Math.log(1.2) } } }))
  const context = await chromium.launchPersistentContext(profile, {
    headless: true, channel: 'chromium', viewport: null, deviceScaleFactor: undefined,
    baseURL: 'http://127.0.0.1:4173', executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    args: ['--window-size=1440,1000'],
  })
  try {
    const page = context.pages()[0]
    await installWorkspaceRefinement(page); await login(page)
    for (const path of [playgroundPath, networkPath]) {
      await page.goto(`http://127.0.0.1:4173${path}`)
      expect(await page.evaluate(() => devicePixelRatio)).toBeCloseTo(factor, 1)
      await page.getByLabel('Theme', { exact: true }).selectOption('dark')
      await expect(page.getByLabel('Theme', { exact: true })).toBeInViewport({ ratio: 1 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
      if (path === playgroundPath) {
        const introduction = page.getByRole('heading', { name: 'Test your Agent', exact: true })
        await introduction.scrollIntoViewIfNeeded()
        await expect(introduction).toBeInViewport({ ratio: 1 })
        await page.getByLabel('Message', { exact: true }).fill(`Unsent text at ${factor}`)
        await page.getByLabel('Theme', { exact: true }).selectOption('light')
        await expect(page.getByLabel('Message', { exact: true })).toHaveValue(`Unsent text at ${factor}`)
        await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeInViewport({ ratio: 1 })
      } else {
        const zoomIn = page.getByRole('button', { name: 'Zoom in', exact: true })
        await zoomIn.scrollIntoViewIfNeeded()
        await expect(zoomIn).toBeInViewport({ ratio: 1 })
      }
    }
  } finally { await context.close() }
})
