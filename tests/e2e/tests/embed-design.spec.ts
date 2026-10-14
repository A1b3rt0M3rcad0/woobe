import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

// Real, independently built woobe-embed iframe; only the HTTP service is a fixture.
const embedBase = process.env.PLAYWRIGHT_EMBED_BASE_URL ?? 'http://127.0.0.1:4181'
const appearance = {
  schema_version: 2, theme: 'light', primary_color: '#2459d3',
  title: 'Woobe support', placeholder: 'Ask about your agent…',
  welcome_message: 'How can I help with your agent deployment?',
}

test('ChatSurface preserves its independent theme and completes a keyboard submission', async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 850 })
  await page.route('**/embed-design-host', route => route.fulfill({
    contentType: 'text/html',
    body: `<!doctype html><html lang="en"><head><title>Woobe ChatSurface fixture</title></head>
      <body style="margin:0;background:#f7f7f4;padding:48px;box-sizing:border-box;height:100vh">
      <iframe id="chat" title="Woobe support" src="/chat-artifact/iframe.html?surface=demo&instance=design"
        style="border:0;width:100%;height:100%;display:block"></iframe></body></html>`,
  }))
  // Serve the independently built artifact on the fixture host without changing its code.
  await page.route('**/chat-artifact/**', async route => {
    const url = new URL(route.request().url())
    const response = await route.fetch({ url: `${embedBase}${url.pathname.replace('/chat-artifact', '')}${url.search}` })
    await route.fulfill({ response })
  })
  await page.route('**/v1/chat/sessions/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/messages:stream')) {
      expect(route.request().postDataJSON().message).toBe('How do I inspect a Run?')
      const event = {
        protocol_version: 2, event_id: 'design-done', run_id: 'design-run',
        session_id: 'design-session', run_kind: 'AGENT', sequence: 1,
        type: 'done', occurred_at: '2026-06-20T12:00:00Z',
        payload: { answer: 'Open Runs, select an execution and inspect its Trace evidence. The selected release stays attached to the Run.' },
      }
      await route.fulfill({ contentType: 'text/event-stream', body: `id: 1\nevent: done\ndata: ${JSON.stringify(event)}\n\n` })
    } else {
      const data = path.endsWith('/surface')
        ? { surface_id: 'demo', name: 'Support', appearance, protocol_version: 1 }
        : path.endsWith('/active-run') ? null : { items: [] }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data }) })
    }
  })
  await page.goto('/embed-design-host')
  const chat = page.frameLocator('#chat')
  await expect(chat.locator('#woobe-chat')).toBeAttached()
  await page.evaluate(({ target }) => {
    const frame = document.querySelector<HTMLIFrameElement>('#chat')!
    frame.contentWindow!.postMessage({
      protocolVersion: 1, instanceId: 'design', surfaceId: 'demo', type: 'init',
      payload: { token: `fixture.${btoa(JSON.stringify({ sid: 'design-session' }))}.unsigned`, hostOrigin: location.origin, apiBaseUrl: location.origin },
    }, target)
  }, { target: new URL(page.url()).origin })
  await expect(chat.getByText('How can I help with your agent deployment?')).toBeVisible()
  const composer = chat.getByRole('textbox')
  await composer.fill('How do I inspect a Run?')
  await composer.press('Enter')
  await expect(chat.getByText(/Open Runs, select an execution/)).toBeVisible()
  await expect(composer).toBeEnabled()
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(accessibility.violations).toEqual([])
  if (process.env.WOOBE_CAPTURE_DOCS === '1') {
    const directory = resolve(process.cwd(), '../../docs/screenshots')
    await mkdir(directory, { recursive: true })
    await page.screenshot({ path: resolve(directory, 'chat-surface.png'), animations: 'disabled' })
  }
})
