import { test,expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { installResources } from '../fixtures/resource-api'
import { respond } from '../fixtures/control-plane'
import { installApi } from '../fixtures/control-plane'

const hosts=[
  ['host-context-manager',/^Change context manager/],['host-execution-strategy',/^Change$/],
  ['host-field-description',/Edit customer_id description/],['host-runtime-context',null],
  ['host-agent-snapshot',/View 1.2.0 snapshot/],['host-http-routes',/^Configure$/],['host-mcp-tools',/^Configure$/],
] as const
for(const width of [1440,768,390])for(const [name,trigger] of hosts)test(`${name} at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1100})
  await installApi(page,{asacAgent:true})
  await page.goto(`/review.html?case=${name}`)
  if(trigger)await page.getByRole('button',{name:trigger}).first().click()
  await expect(page.getByRole('dialog').last()).toBeVisible()
  await expect(page.locator('[data-review-error]')).toHaveCount(0)
  await page.evaluate(()=>document.fonts.ready)
  if(process.env.WOOBE_CAPTURE_DOCS==='1'){
    const directory=resolve(process.cwd(),'../../docs/screenshots/v2/overlays',name);await mkdir(directory,{recursive:true})
    await page.screenshot({path:resolve(directory,`${width}px.png`),animations:'disabled'})
  }
})

for(const width of [1440,768,390])test(`secondary confirmations and input bindings at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1100});await installApi(page,{asacAgent:true})
  const capture=async(name:string)=>{
    await page.evaluate(()=>document.fonts.ready)
    const dialog=page.getByRole('dialog').last()
    const bounds=await dialog.boundingBox();expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(width+1)
    if(process.env.WOOBE_CAPTURE_DOCS!=='1')return
    const directory=resolve(process.cwd(),'../../docs/screenshots/v2/overlays',name);await mkdir(directory,{recursive:true})
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
  await page.route('**/configuration/keys/config-demo/**',route=>respond(route,{items:new URL(route.request().url()).pathname.endsWith('/usage') ? [{consumer_kind:'tool',consumer_id:'tool-demo',definition_revision:'1',field_path:'config.url',required:true,destination:'https://example.test/support'}] : [{id:'policy-demo',consumer_kind:'tool',consumer_scope:'tool-demo',destination:'https://example.test/support',field_paths:['config.url'],environments:['draft'],revision:1,revoked:false}],total:1,offset:0,limit:50}))
  await page.goto('/review.html?case=ConfigurationUsageDialog')
  await page.getByRole('button',{name:'Approve for draft',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'Approve use in draft?'})).toBeVisible()
  await capture('ConfigurationApproveUse')
  await page.keyboard.press('Escape')
  await page.getByRole('button',{name:'Revoke',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'Revoke this approval?'})).toBeVisible()
  await capture('ConfigurationRevokeUse')
})
