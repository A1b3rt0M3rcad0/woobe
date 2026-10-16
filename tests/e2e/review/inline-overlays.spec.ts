import { test,expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { captureScrollSequence, resetCaptures } from './capture'
import { installResources } from '../fixtures/resource-api'
import { installConfigurationReviewApi } from './configuration-api'
import { respond } from '../fixtures/control-plane'
import { installApi } from '../fixtures/control-plane'

const hosts=[
  ['host-agent-result',/^View full result$/],['host-config-legacy',/^Convert draft$/],['host-network-history',null],
  ['host-context-manager',/^Change context manager/],['host-execution-strategy',/^Change$/],
  ['host-field-description',/Edit customer_id description/],['host-runtime-context',null],
  ['host-agent-snapshot',/View 1.2.0 snapshot/],['host-http-routes',/^Configure$/],['host-mcp-tools',/^Configure$/],
] as const
for(const width of [1440,768,390])for(const [name,trigger] of hosts)test(`${name} at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1100})
  await installApi(page,{asacAgent:true})
  await page.route('**/configuration/legacy-bindings*',route=>respond(route,{items:[{id:'legacy-demo',key_id:'config-demo',key:'SUPPORT_ENDPOINT',source_kind:'provider_credential',source_id:'credential-demo',field_path:'base_url',revision:1,state:'active',source:'legacy_compat',material:'present'}],total:1}))
  await page.route('**/asac/**',route=>new URL(route.request().url()).pathname.startsWith('/projects/') ? respond(route,{drafts:[],records:[],watermark:0,has_more:false,next_cursor:null,snapshot_id:null,environment_generation:0,selection_authority:'asac'}) : route.fallback())
  await page.goto(`/review.html?case=${name}`)
  await expect(page.locator('[data-review-ready]')).toBeVisible()
  await expect(page.locator('[data-review-error]')).toHaveCount(0)
  if(trigger)await page.getByRole('button',{name:trigger}).first().click()
  await expect(page.getByRole('dialog').last()).toBeVisible()
  await expect(page.locator('[data-review-error]')).toHaveCount(0)
  if(name==='host-context-manager') {
    const panel=page.getByRole('dialog').locator('section');expect((await panel.boundingBox())!.width).toBeGreaterThan(250)
    await expect(page.getByRole('dialog').getByRole('button',{name:'Selected',exact:true})).toBeInViewport({ratio:1})
  }
  await page.evaluate(()=>document.fonts.ready)
  if(process.env.WOOBE_CAPTURE_AUXILIARY==='1'){
    const directory=resolve(process.cwd(),'review-results/captures/overlays',name);await mkdir(directory,{recursive:true})
    await resetCaptures(directory,`${width}px`)
    await page.screenshot({path:resolve(directory,`${width}px.png`),animations:'disabled'})
    await captureScrollSequence(page,page.getByRole('dialog').last(),directory,`${width}px`)
    if(name==='host-agent-result') {
      await page.getByRole('button',{name:/^raw$/i}).click()
      await expect(page.getByText('Raw response',{exact:true})).toBeVisible()
      await page.screenshot({path:resolve(directory,`${width}px-raw.png`),animations:'disabled'})
    }
    if(name==='host-network-history' && width===1440)for(const tab of ['revisions','releases','deployments']) {
      await page.getByRole('tab',{name:new RegExp(`^${tab}$`,'i')}).click()
      await expect(page.locator('[data-review-error]')).toHaveCount(0)
      await page.screenshot({path:resolve(directory,`section-${tab}.png`),animations:'disabled'})
      await captureScrollSequence(page,page.getByRole('dialog').last(),directory,`section-${tab}`)
    }
  }
})

for(const width of [1440,768,390])test(`secondary confirmations and input bindings at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1100});await installApi(page,{asacAgent:true})
  const capture=async(name:string)=>{
    await page.evaluate(()=>document.fonts.ready)
    const dialog=page.getByRole('dialog').last()
    const bounds=await dialog.boundingBox();expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(width+1)
    if(process.env.WOOBE_CAPTURE_AUXILIARY!=='1')return
    const directory=resolve(process.cwd(),'review-results/captures/overlays',name);await mkdir(directory,{recursive:true})
    await resetCaptures(directory,`${width}px`)
    await page.screenshot({path:resolve(directory,`${width}px.png`),animations:'disabled'})
  }
  await page.goto('/review.html?case=host-mcp-tools')
  await page.getByRole('button',{name:'Configure',exact:true}).click()
  await page.getByRole('button',{name:'Inputs',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'Input bindings: support_lookup'})).toBeVisible()
  await capture('McpInputBindings')
  await installResources(page)
  await page.goto('/review.html?case=CollectionDetailsModalV2-CollectionDetailsModal')
  await page.getByRole('button',{name:'Delete Support handbook',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'Delete document',exact:true})).toBeVisible()
  await capture('CollectionDeleteDocument')
  await installConfigurationReviewApi(page)
  await page.goto('/review.html?case=ConfigurationUsageDialog')
  await expect(page.getByRole('button',{name:'Approve use in Draft',exact:true})).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await capture('ConfigurationApproveUse')
  await page.getByRole('button',{name:'Approve use in Draft',exact:true}).click()
  await expect(page.getByText('Use approved in Draft',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Revoke access',exact:true}).click()
  await expect(page.getByRole('region',{name:'Confirm access revocation'})).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await capture('ConfigurationRevokeUse')
})
