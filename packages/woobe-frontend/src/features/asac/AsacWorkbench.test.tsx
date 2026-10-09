// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api/errors'
import { AsacWorkbench } from './AsacWorkbench'

const fixture = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), put: vi.fn(), refetch: vi.fn(), generation: 1,
  draft: {draft_id:'draft-1',resource_uid:'uid-1',name:'hotfix',generation:1,working_revision_id:null,origin:{environment:'production',snapshot_id:'release-1'},definition_digest:'sha256:a'},
}))
vi.mock('@/lib/api/client', () => ({get:fixture.get,post:fixture.post,put:fixture.put}))
vi.mock('@tanstack/react-query', () => ({useQuery: ({queryKey}: {queryKey:string[]}) => ({
  data: queryKey[0] === 'asac-drafts' ? {drafts:[fixture.draft]} : queryKey[0] === 'asac-draft' ? {...fixture.draft,generation:fixture.generation} : {snapshot_id:'release-1',environment_generation:7},
  isError:false,refetch:fixture.refetch,
})}))
vi.mock('@/components/ui/Select', () => ({Select: ({options,placeholder,...props}: {options:{value:string,label:string}[],placeholder?:string}) => <select {...props}>{placeholder && <option value="">{placeholder}</option>}{options.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select>}))
let root: Root, container: HTMLDivElement
const editor = () => ({draft:{...fixture.draft},entrypoint_path:'agent.yaml',files:[{path:'agent.yaml',editable:true,content:'objective: original\n'}]})
const render = () => root.render(<AsacWorkbench projectId="p" resourceId="a" kind="Agent" />)
const button = (name:string) => Array.from(container.querySelectorAll('button')).find(item=>item.textContent===name)!
async function click(name:string) { await act(async()=>button(name).click()) }
async function load() {
  await act(async()=>{const select=container.querySelector('[aria-label="Isolated Draft"]') as HTMLSelectElement;select.value='draft-1';select.dispatchEvent(new Event('change',{bubbles:true}))})
  await click('Load saved files')
}
beforeEach(async()=>{
  Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true}); sessionStorage.clear(); vi.clearAllMocks();fixture.generation=1
  fixture.get.mockImplementation(async(path:string)=>path.endsWith('/editor') ? editor() : {})
  container=document.createElement('div');document.body.append(container);root=createRoot(container)
  await act(async()=>render())
})
afterEach(async()=>{await act(async()=>root.unmount());container.remove()})
describe('Owner lifecycle workbench',()=>{
  it('keeps local edits when a remote generation changes and blocks the stale write',async()=>{
    await load()
    const textarea=container.querySelector('[aria-label="Author YAML"]') as HTMLTextAreaElement
    await act(async()=>{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(textarea,'objective: changed\n');textarea.dispatchEvent(new Event('input',{bubbles:true}))})
    fixture.generation=2;await act(async()=>render())
    expect(textarea.value).toBe('objective: changed\n')
    expect(container.textContent).toContain('Your edits remain here')
    expect(button('Save this Draft').disabled).toBe(true)
    expect(fixture.put).not.toHaveBeenCalled()
  })
  it('blocks writes after an ambiguous response and recovers the original operation without POST retry',async()=>{
    fixture.post.mockImplementation(async(path:string)=>{if(path.includes('/packages/export'))return {source:{resource_uid:'uid-1'},export_id:'export-1'};throw new ApiError('Lost response',503)})
    await click('Open isolated Draft')
    expect(container.textContent).toContain('Uncertain open operation')
    expect(button('Open isolated Draft').disabled).toBe(true)
    const checkpoint=JSON.parse(sessionStorage.getItem('woobe-asac-pending:p:Agent:a')!)
    expect(checkpoint).not.toHaveProperty('files');expect(checkpoint).not.toHaveProperty('leases')
    fixture.get.mockResolvedValue({state:'committed',result:fixture.draft})
    await click('Reconcile original operation')
    expect(fixture.get).toHaveBeenLastCalledWith(expect.stringContaining('/operations/'+checkpoint.operation_id),{sensitive:true})
    expect(fixture.post).toHaveBeenCalledTimes(2)
    expect(sessionStorage.length).toBe(0)
  })
  it('does not create an unreconcilable checkpoint when source capture fails',async()=>{
    fixture.post.mockRejectedValue(new ApiError('Capture failed',503))
    await click('Open isolated Draft')
    expect(sessionStorage.length).toBe(0)
    expect(button('Open isolated Draft').disabled).toBe(false)
    expect(fixture.post).toHaveBeenCalledTimes(1)
  })
  it('clears a known rejected write while preserving the refusal explanation',async()=>{
    fixture.post.mockImplementation(async(path:string)=>{if(path.includes('/packages/export'))return {source:{resource_uid:'uid-1'},export_id:'export-1'};throw new ApiError('Draft name conflict',409)})
    await click('Open isolated Draft')
    expect(sessionStorage.length).toBe(0)
    expect(container.textContent).toContain('Draft name conflict')
    expect(button('Open isolated Draft').disabled).toBe(false)
  })
})
