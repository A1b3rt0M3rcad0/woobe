import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import type { Page } from '@playwright/test'
import pages from '../fixtures/main-pages.json'

/** Documentation intentionally contains only main pages, one image per viewport. */
export async function captureMainPage(page: Page, surface: string, width: number) {
  const entry = pages.find(item => item.surface === surface)
  if (process.env.WOOBE_CAPTURE_DOCS !== '1' || !entry) return
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
  })
  const folder = width === 1440 ? '' : width === 768 ? 'tablet' : 'mobile'
  const directory = resolve(process.cwd(), '../../docs/screenshots', folder)
  await mkdir(directory, { recursive: true })
  await page.screenshot({ path: resolve(directory, `${entry.slug}.png`), animations: 'disabled' })
}
