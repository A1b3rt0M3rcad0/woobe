import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { readFile } from 'node:fs/promises'
import { installApi, login, respond, workspace, project } from '../fixtures/control-plane'
import { emptyUsage } from '../fixtures/design-gallery'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'
import { installResources } from '../fixtures/resource-api'

const root=`/workspaces/${workspace.id}/projects/${project.id}`
const surfaces=[
  ['workspaces','/workspaces'],['workspace-projects',`/workspaces/${workspace.id}/projects`],
  ['workspace-settings',`/workspaces/${workspace.id}/settings`],['workspace-setup',`/workspaces/${workspace.id}/setup`],
  ['project-settings',`${root}/settings`],['project-setup',`${root}/setup`],
  ['account-settings','/settings'],['mcp-callback','/mcp/oauth/callback'],
  ['overview',root],...['agents','networks','knowledge','tools','skills','models','credentials','api-keys','chat-surfaces','environments','usage','traces'].map(name=>[name,`${root}/${name}`]),
  ['playground',`${root}/agents/agent-asac/playground`],['network-workspace',`${root}/networks/network-support`],
]

for(const width of [1440,768,390]) for(const [name,url] of surfaces) test(`complete surface ${name} at ${width}px`,async({page})=>{
  await page.clock.setFixedTime(new Date('2026-06-20T12:00:00Z'))
  await page.setViewportSize({width,height:1100})
  const errors:string[]=[]; page.on('pageerror',error=>errors.push(error.message))
  await installApi(page,{asacAgent:true})
  await page.route('**/core/projects/project-a/overview*',route=>respond(route,projectOverviewFixture))
  await page.route('**/metering/projects/project-a/usage*',route=>respond(route,emptyUsage))
  await page.route('**/core/projects/project-a/configuration/keys*',route=>respond(route,{items:[],total:0,offset:0,limit:50,permissions:{declare:true,'value:write':true}}))
  await page.route('**/core/projects/project-a/runs*',route=>respond(route,{summary:{agent_runs:0,direct_agent_runs:0,network_agent_runs:0,network_runs:0,active_top_level_runs:0,failed_top_level_runs:0,top_level_runs:0,failure_rate_percent:0,p95_top_level_latency_ms:null,avg_agent_runs_per_network_run:null},direct_agent_runs:[],network_runs:[]}))
  await login(page); await page.goto(url)
  if(name.endsWith('settings')) await expect(page.getByRole('dialog').first()).toBeVisible()
  else await expect(page.locator('#main-content')).not.toBeEmpty()
  await expect(page.getByText('Something went wrong',{exact:true})).toHaveCount(0)
  await page.evaluate(()=>document.fonts.ready)
  await page.waitForTimeout(250)
  expect(errors).toEqual([])
  const directory=resolve(process.cwd(),'../../docs/screenshots/v2/pages',name)
  if(process.env.WOOBE_CAPTURE_DOCS==='1') {
    await mkdir(directory,{recursive:true})
    await page.screenshot({path:resolve(directory,`${width}px.png`),animations:'disabled'})
    const scroller=page.locator('#main-content')
    if(await scroller.count()) {
      const dimensions=await scroller.evaluate(el=>({height:el.clientHeight,total:el.scrollHeight}))
      for(let top=dimensions.height-80,index=2;top<dimensions.total;top+=dimensions.height-80,index++) {
        await scroller.evaluate((el,y)=>{el.scrollTop=y},top)
        await page.screenshot({path:resolve(directory,`${width}px-content-${index}.png`),animations:'disabled'})
      }
    }
  }
})

test('populated resource catalogs, cost attribution and the Run ledger',async({page})=>{
  test.setTimeout(90_000)
  await page.setViewportSize({width:1440,height:1100})
  await page.clock.setFixedTime(new Date('2026-06-20T12:00:00Z'))
  await installApi(page,{asacAgent:true});await installResources(page);await login(page)
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message))
  for(const segment of ['knowledge','tools','skills','models','credentials','api-keys','chat-surfaces','usage','traces']) {
    await page.goto(`${root}/${segment}`)
    await expect(page.locator('#main-content h1')).toBeVisible()
    await expect(page.getByText('Something went wrong',{exact:true})).toHaveCount(0)
    await page.waitForTimeout(200);await page.evaluate(()=>document.fonts.ready)
    if(process.env.WOOBE_CAPTURE_DOCS==='1') {
      const directory=resolve(process.cwd(),'../../docs/screenshots/v2/pages',segment);await mkdir(directory,{recursive:true})
      await page.screenshot({path:resolve(directory,'populated.png'),animations:'disabled'})
      const scroller=page.locator('#main-content')
      const total=await scroller.evaluate(el=>el.scrollHeight)
      for(let top=900,index=2;top<total;top+=900,index++){
        await scroller.evaluate((el,y)=>{el.scrollTop=y},top)
        await page.screenshot({path:resolve(directory,`populated-content-${index}.png`),animations:'disabled'})
      }
    }
  }
  expect(errors).toEqual([])
})

test('every compatibility route resolves to its canonical surface',async({page})=>{
  test.setTimeout(90_000)
  await installApi(page,{asacAgent:true});await login(page)
  const router=await readFile(resolve(process.cwd(),'../../packages/woobe-frontend/src/app/router.tsx'),'utf8')
  const paths=[...router.matchAll(/<Route path="([^"]+)"/g)].map(match=>match[1])
    .filter(path=>path==='/' || path==='/dashboard' || path.startsWith('/projects') || path==='/workspaces/:workspaceId' || /\/agents\/(?:new|:agentId(?:\/edit)?)$/.test(path) || path.endsWith('/network'))
  for(const path of paths) {
    const target=path.replaceAll(':workspaceId',workspace.id).replaceAll(':projectId',project.id).replaceAll(':agentId','agent-asac').replaceAll(':networkId','network-support')
    await test.step(target,async()=>{
      await page.goto(target)
      await expect(page).toHaveURL(/\/workspaces(?:\/|$)/)
      await expect(page.getByText('404 / route not found',{exact:true})).toHaveCount(0)
    })
  }
})

for(const [name,url,fresh] of [['sign-in','/login',false],['register','/register',true],['not-found','/missing-page',false]] as const) test(`public surface ${name}`,async({page})=>{
  await installApi(page,{freshCore:fresh})
  await page.setViewportSize({width:1440,height:1100});await page.goto(url)
  await expect(page.locator('h1,h2').first()).toBeVisible()
  await page.evaluate(()=>document.fonts.ready)
  if(process.env.WOOBE_CAPTURE_DOCS==='1') {
    const directory=resolve(process.cwd(),'../../docs/screenshots/v2/pages',name);await mkdir(directory,{recursive:true})
    await page.screenshot({path:resolve(directory,'desktop.png'),animations:'disabled'})
    await page.setViewportSize({width:390,height:844})
    await page.screenshot({path:resolve(directory,'mobile.png'),fullPage:true,animations:'disabled'})
  }
})

test('compact viewport and enlarged text preserve essential controls',async({page})=>{
  await installApi(page,{asacAgent:true});await login(page)
  for(const width of [320,640]) {
    await page.setViewportSize({width,height:1000})
    await page.goto(`${root}/agents`)
    if(width===640)await page.addStyleTag({content:'html { font-size: 200% !important; }'})
    await expect(page.getByRole('button',{name:/Create Agent/}).first()).toBeVisible()
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1)
    if(process.env.WOOBE_CAPTURE_DOCS==='1') {
      const directory=resolve(process.cwd(),'../../docs/screenshots/v2/states');await mkdir(directory,{recursive:true})
      await page.screenshot({path:resolve(directory,width===320?'agents-320px.png':'agents-enlarged-root-text.png'),animations:'disabled',fullPage:true})
    }
  }
})
