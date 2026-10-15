import { test,expect,type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { installApi,login,respond,project,workspace } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'
import { apiKey } from '../fixtures/resource-data'

const root=`/workspaces/${workspace.id}/projects/${project.id}`
async function setup(page:Page) {await installApi(page,{asacAgent:true});await installResources(page);await login(page)}
async function shot(page:Page,name:string) {
  await page.evaluate(()=>document.fonts.ready)
  if(process.env.WOOBE_CAPTURE_AUXILIARY!=='1')return
  const directory=resolve(process.cwd(),'review-results/captures/flows');await mkdir(directory,{recursive:true})
  await page.screenshot({path:resolve(directory,`${name}.png`),animations:'disabled'})
}

for(const width of [1440,390])test(`page creation overlays and credential lifecycle at ${width}px`,async({page})=>{
  test.setTimeout(60_000)
  await page.setViewportSize({width,height:1100});await setup(page)
  await page.goto(`${root}/networks`);await page.getByRole('button',{name:'Create Network',exact:true}).first().click()
  await expect(page.getByRole('dialog')).toBeVisible();await shot(page,`create-network-${width}`);await page.keyboard.press('Escape')
  await page.goto(`${root}/chat-surfaces`);await page.getByRole('button',{name:'Publish ChatSurface',exact:true}).first().click()
  await expect(page.getByRole('dialog')).toBeVisible();await shot(page,`create-chat-surface-${width}`);await page.keyboard.press('Escape')
  await page.goto(`${root}/credentials`);await page.getByRole('button',{name:'Open provider connection Development provider'}).click()
  await expect(page.getByRole('dialog')).toBeVisible();await shot(page,`credential-details-${width}`)
  await page.getByText('Revoke or archive connection', {exact:true}).click()
  await page.getByRole('button',{name:'Revoke',exact:true}).click()
  const revoke = page.getByRole('dialog',{name:'Revoke credential',exact:true})
  await expect(revoke).toBeVisible()
  await expect(revoke.getByRole('button',{name:'Close dialog',exact:true})).toBeFocused()
  await shot(page,`credential-revoke-${width}`);await page.keyboard.press('Escape')
  await expect(revoke).not.toBeVisible()
  await page.getByRole('button',{name:'Open provider connection Development provider'}).click()
  await page.getByText('Revoke or archive connection', {exact:true}).click()
  await page.getByRole('button',{name:'Archive',exact:true}).click();await shot(page,`credential-archive-${width}`)
})

test('Runtime Key management, revocation and synthetic secret reveal',async({page})=>{
  await setup(page)
  await page.goto(`${root}/api-keys?type=runtime&targetType=agent&target=agent-asac&credential=credential-demo-key`)
  await expect(page.getByRole('dialog').first()).toBeVisible();await shot(page,'runtime-key-management')
  await page.getByRole('button',{name:'Revoke',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'Revoke API key',exact:true})).toBeVisible();await shot(page,'runtime-key-revoke')
  await page.keyboard.press('Escape')
  await page.getByRole('button',{name:'Rotate',exact:true}).click()
  await page.route('**/api-keys/key-demo/rotate',route=>respond(route,{...apiKey,key:'wb_demo_not_a_real_secret'}))
  await page.getByRole('button',{name:'Rotate key',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'New API key secret',exact:true})).toBeVisible();await shot(page,'runtime-key-synthetic-secret')
})

test('project switcher and mobile navigation expose their complete open states',async({page})=>{
  await setup(page);await page.goto(`${root}/agents`)
  await page.getByRole('button',{name:'Release Project Woobe Test Workspace',exact:true}).click()
  await expect(page.getByText('Switch project',{exact:true})).toBeVisible();await shot(page,'project-switcher')
  await page.setViewportSize({width:390,height:1100})
  await page.getByRole('button',{name:'Open navigation'}).click()
  await expect(page.getByRole('dialog',{name:'Navigation'})).toBeVisible();await shot(page,'mobile-navigation')
})

for(const state of ['empty','error','loading'] as const)test(`Agent inventory ${state} state`,async({page})=>{
  await setup(page)
  let release:()=>void=()=>{}
  const gate=new Promise<void>(resolve=>{release=resolve})
  await page.route('**/ai/agents?*',async route=>{
    if(state==='loading')await gate
    await respond(route,state==='error'?null:[],state==='error'?500:200)
  })
  await page.goto(`${root}/agents`)
  await expect(page.getByRole('heading',{name:'Agents',level:1,exact:true})).toBeVisible()
  await page.waitForTimeout(state==='error'?1200:150)
  await shot(page,`agents-${state}`);release()
})
