import { test, expect, type CDPSession, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import cases from './overlay-cases.json'
import { captureScrollSequence, resetCaptures } from './capture'
import { installApi, respond, productionAgent, selectedRelease, project, workspace, now } from '../fixtures/control-plane'
import { DEFAULT_CHAT_SURFACE_APPEARANCE } from '../../../packages/woobe-frontend/src/features/chat-surfaces/appearance'
import { hasRenderedFont, platformFontFamily } from '../support/font-evidence'

const captures = resolve(process.cwd(), 'review-results/captures')

async function prepare(page: Page) {
  await page.clock.setFixedTime(new Date('2026-10-14T12:00:00Z'))
  await installApi(page, { asacAgent: true })
  await page.route('**/*', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.includes('/configuration/') && !path.includes('/src/')) return respond(route, { items: [], total: 0, offset: 0, limit: 50, permissions: { declare: true, 'value:write': true } })
    if (path.endsWith('/promotions/preview')) return respond(route, { nodes: [], actions: [], missing_agent_ids: [], ready: true, network_revision: 1, network_version_id: null, environment: 'staging' })
    if (path.startsWith('/ai/skills') || path.startsWith('/skills')) return respond(route, [])
    if (path === '/ai/credentials') return respond(route, [{ id:'credential-demo', project_id:project.id, provider:'openai', name:'Development provider', status:'active' }])
    if (path === '/ai/provider-models') return respond(route, [{ id:'model-demo',project_id:project.id,provider_credential_id:'credential-demo',provider:'openai',name:'Review model',model:'review-model',model_type:'generation',spec:{},metadata:{},status:'active' }])
    if (path.endsWith('/test-sessions')) return respond(route,{session_id:'session-demo',target_release_id:selectedRelease.id,session_token:`fixture.${Buffer.from(JSON.stringify({sid:'session-demo'})).toString('base64url')}.unsigned`,expires_in:3600,source:'control_plane_test'})
    if (path.startsWith('/v1/chat/sessions/')) return respond(route,path.endsWith('/surface') ? {surface_id:'surface-public-demo',name:'Support assistant',appearance:{...DEFAULT_CHAT_SURFACE_APPEARANCE,theme:'light',welcome_message:'A synthetic test conversation.'},protocol_version:1} : path.endsWith('/active-run') ? null : {items:[]})
    if (path === '/chat-surfaces/surface-demo') return respond(route, { id:'surface-demo', public_id:'surface-public-demo',project_id:project.id,name:'Support assistant',target_type:'agent',target_id:productionAgent.id,target_release_id:selectedRelease.id,environment:'production',status:'active',access_mode:'backend_managed',allowed_origins:['https://example.test'],appearance_config:DEFAULT_CHAT_SURFACE_APPEARANCE,requests_per_minute:60,max_concurrent_runs:2,session_token_ttl_seconds:3600,token_epoch:1,created_at:now,updated_at:now })
    if (path.startsWith('/chat-surfaces/')) return respond(route, [])
    await route.fallback()
  })
}

async function fonts(page: Page) {
  await page.evaluate(async () => {
    const text='Usage Cap · PR Reviewer · $312.40 / $380 · 0123456789 · I l 1 O 0 · ação conexão utilização'
    for (const family of ['JetBrains Mono','Inter']) for (const weight of [400,500]) {
      const faces=await document.fonts.load(`${weight} 14px "${family}"`,text)
      if (!faces.length || faces.some(face=>face.status!=='loaded')) throw new Error(`Font missing: ${family} ${weight}`)
    }
    await document.fonts.ready
  })
}

async function paintedFonts(client: CDPSession, nodeId: number) {
  const result = await client.send('CSS.getPlatformFontsForNode', { nodeId })
  if (result.fonts.some(font => font.glyphCount > 0)) return { ...result, probeSource: 'element' }
  // Native textareas paint inside a user-agent shadow root; CodeMirror paints token spans.
  const { node } = await client.send('DOM.describeNode', { nodeId, depth: -1, pierce: true })
  const pending = [...(node.shadowRoots ?? []), ...(node.children ?? [])]
  while (pending.length) {
    const child = pending.shift()!
    if (child.nodeType === 1 && child.children?.some(text => text.nodeType === 3 && text.nodeValue.trim())) {
      const { nodeIds } = await client.send('DOM.pushNodesByBackendIdsToFrontend', { backendNodeIds: [child.backendNodeId] })
      const painted = await client.send('CSS.getPlatformFontsForNode', { nodeId: nodeIds[0] })
      if (painted.fonts.some(font => font.glyphCount > 0)) return { ...painted, probeSource: 'painted descendant or native shadow text' }
    }
    pending.push(...(child.shadowRoots ?? []), ...(child.children ?? []))
  }
  return { ...result, probeSource: 'no painted glyphs' }
}

async function capture(page: Page, folder: string, name: string) {
  if (process.env.WOOBE_CAPTURE_AUXILIARY !== '1') return
  await mkdir(resolve(captures,folder),{recursive:true})
  await page.screenshot({path:resolve(captures,folder,`${name}.png`),animations:'disabled',fullPage:true})
}

test('nested dialogs, focus return and JSON expansion', async ({page})=>{
  await prepare(page)
  await page.goto('/review.html?case=ConfigurationValueEditor')
  const clear=page.getByRole('button',{name:'Clear value',exact:true})
  await clear.click()
  await expect(page.getByRole('dialog')).toHaveCount(2)
  await capture(page,'states','configuration-clear-confirmation')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await expect(clear).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.goto('/review.html?case=primitives')
  const expand=page.getByRole('button',{name:'Expand JSON',exact:true})
  await expand.click()
  await expect(page.getByRole('dialog',{name:'JSON',exact:true})).toBeVisible()
  await capture(page,'overlays/JsonCodeBlock','expanded')
  await page.keyboard.press('Escape')
  await expect(expand).toBeFocused()
})

test('hover, focus, copy confirmation, selected tabs and unavailable runtime states',async({page})=>{
  await prepare(page)
  await page.goto('/review.html?case=primitives')
  const primary=page.getByRole('button',{name:'default',exact:true})
  await primary.hover();await capture(page,'states','button-hover')
  await primary.focus();await capture(page,'states','button-focus')
  const agents=page.getByRole('tab',{name:'Agents',exact:true})
  await agents.focus();await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab',{name:'Networks',exact:true})).toHaveAttribute('aria-selected','true')
  await capture(page,'states','tabs-selected-keyboard')
  await page.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:new URL(page.url()).origin})
  const copy=page.locator('[data-sample=code]').getByRole('button',{name:'Copy',exact:true}).last()
  await copy.click()
  await expect(page.getByRole('button',{name:'Copied',exact:true})).toBeVisible()
  await capture(page,'states','copy-confirmation')
  await page.goto('/review.html?case=NetworkRuntimeControlsPopover')
  await page.route('**/runtime-environments*',route=>respond(route,null,500))
  await page.reload();await page.locator('main button').first().click()
  await expect(page.getByRole('region',{name:'Network runtime controls'})).toContainText('State unavailable')
  await capture(page,'states','network-runtime-unavailable')
})

test('production primitives, variants and actual rendered fonts', async ({ page }) => {
  await prepare(page)
  await page.goto('/review.html?case=primitives')
  await expect(page.locator('[data-sample=buttons]')).toBeVisible()
  await expect(page.locator('[data-review-error]')).toHaveCount(0)
  await fonts(page)
  const client=await page.context().newCDPSession(page)
  await client.send('DOM.enable'); await client.send('CSS.enable')
  const {root}=await client.send('DOM.getDocument')
  const evidence=[]
  for (const [selector,family] of [
    ['[data-sample=panels] h3','JetBrains Mono'],
    ['[data-sample=panels] p','Inter'],
    ['[data-sample=panels] .text-metric','JetBrains Mono'],
    ['[data-font-probe=mono]','JetBrains Mono'],
    ['[data-font-probe=sans]','Inter'],
    ['[data-sample=fields] label[for=review-name]','Inter'],
    ['#review-name','Inter'],
    ['[data-sample=fields] textarea','Inter'],
    ['[data-sample=buttons] button','Inter'],
    ['[data-sample=code] .cm-line','JetBrains Mono'],
    ['[data-sample=tables] th','JetBrains Mono'],
    ['[data-sample=tables] h1','serif'],
  ] as const) {
    // CDP reports painted glyphs; native textarea text below the viewport may have none yet.
    await page.locator(selector).first().scrollIntoViewIfNeeded()
    await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))))
    const {nodeId}=await client.send('DOM.querySelector',{nodeId:root.nodeId,selector})
    const result=await paintedFonts(client,nodeId)
    if(family==='serif') {
      expect(result.fonts.some(font=>font.glyphCount>0 && !['Inter','JetBrains Mono'].includes(platformFontFamily(font.familyName)))).toBeTruthy()
      if(process.env.WOOBE_REQUIRE_GEORGIA==='1')expect(hasRenderedFont(result.fonts,'Georgia','system')).toBeTruthy()
    } else expect(hasRenderedFont(result.fonts,family,'web'),JSON.stringify({selector,family,fonts:result.fonts})).toBeTruthy()
    const computed=await page.locator(selector).first().evaluate(el=>{const style=getComputedStyle(el);return {family:style.fontFamily,weight:style.fontWeight,size:style.fontSize}})
    evidence.push({selector,expected:family,fonts:result.fonts,computed,probeSource:result.probeSource})
  }
  for (const sample of await page.locator('[data-sample]').all()) {
    const name=(await sample.getAttribute('data-sample'))!
    if(process.env.WOOBE_CAPTURE_AUXILIARY==='1') {
      await mkdir(resolve(captures,'components'),{recursive:true})
      await sample.screenshot({path:resolve(captures,'components',`${name}.png`),animations:'disabled'})
    }
  }
  await page.getByRole('button',{name:'Open actions',exact:true}).click()
  await expect(page.getByRole('button',{name:'Inspect release',exact:true})).toBeVisible()
  await capture(page,'overlays/Dropdown','open')
  if(process.env.WOOBE_CAPTURE_DOCS==='1') {
    const directory=resolve(process.cwd(),'../../docs/design/fonts')
    await mkdir(directory,{recursive:true})
    await writeFile(resolve(directory,'primitives.json'),JSON.stringify({browser:page.context().browser()?.version(),evidence},null,2)+'\n')
  }
})

for (const width of [1440,768,390]) for (const item of cases) test(`overlay ${item.id} at ${width}px`, async ({page})=>{
  await page.setViewportSize({width,height:1100})
  const errors:string[]=[]; page.on('pageerror',error=>errors.push(error.message))
  await prepare(page)
  await page.goto(`/review.html?case=${encodeURIComponent(item.id)}`)
  await expect(page.locator('[data-review-ready]')).toBeVisible()
  await expect(page.locator('[data-review-error]')).toHaveCount(0)
  await fonts(page)
  if(item.id.includes('Popover')) await page.locator('main button').first().click()
  const overlay=item.id.includes('Popover') ? page.getByRole('region',{name:/runtime controls/}) : page.getByRole('dialog').first()
  await expect(overlay).toBeVisible()
  if(item.id==='ChatSurfaceLiveTestDialog') {
    await expect(page.frameLocator('iframe').getByRole('textbox')).toBeVisible()
    const frame=await page.locator('iframe').boundingBox();const metadata=await page.locator('aside').boundingBox()
    if(width<1024)expect(frame!.y+frame!.height).toBeLessThanOrEqual(metadata!.y)
    else expect(frame!.x+frame!.width).toBeLessThanOrEqual(metadata!.x)
  }
  if(['AgentManagerModal','NetworkVersionsModalV2-NetworkVersionsModal'].includes(item.id)) {
    for(const button of await overlay.locator('footer button').all())await expect(button).toBeInViewport({ratio:1})
  }
  await page.waitForTimeout(150)
  expect(errors).toEqual([])
  const title=overlay.locator('h2').first()
  if(await title.count())expect(await title.evaluate(el=>el.scrollWidth-el.clientWidth),'Dialog titles must wrap without hiding their scope').toBeLessThanOrEqual(1)
  const bounds=await overlay.boundingBox()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(width+1)
  expect(await overlay.evaluate(el=>el.scrollWidth-el.clientWidth),'The dialog must not clip horizontal content').toBeLessThanOrEqual(1)
  await resetCaptures(resolve(captures,'overlays',item.id),`${width}px`)
  if(width===1440)await resetCaptures(resolve(captures,'overlays',item.id),'section')
  await capture(page,`overlays/${item.id}`,`${width}px`)
  await captureScrollSequence(page,overlay,resolve(captures,'overlays',item.id),`${width}px`)
  if(width===1440 && !item.id.includes('Popover')) {
    const sections=overlay.locator('aside nav button,[role=tab],[role=group][aria-label*="sections"] button')
    const labels=await sections.allTextContents()
    for(let index=0;index<labels.length;index++) {
      const button=sections.nth(index)
      if(!await button.isVisible() || !await button.isEnabled()) continue
      await button.click()
      await expect(page.locator('[data-review-error]')).toHaveCount(0)
      await page.waitForTimeout(100)
      expect(errors).toEqual([])
      const name=`section-${index+1}-${labels[index].trim().toLowerCase().replace(/[^a-z0-9]+/g,'-')}`
      await capture(page,`overlays/${item.id}`,name)
      await captureScrollSequence(page,overlay,resolve(captures,'overlays',item.id),name)
    }
  }
})
