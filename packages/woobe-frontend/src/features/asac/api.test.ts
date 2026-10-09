import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ledgerPage, leaseProof, saveEditor } from './api'
const fixture = vi.hoisted(()=>({get:vi.fn(),put:vi.fn()}))
vi.mock('@/lib/api/client',()=>({get:fixture.get,put:fixture.put,post:vi.fn()}))
beforeEach(()=>vi.clearAllMocks())
describe('Owner workbench API',()=>{
  it('rejects an incomplete cursor or a different observation watermark',async()=>{
    fixture.get.mockResolvedValue({records:[],watermark:'first',has_more:true,next_cursor:null})
    await expect(ledgerPage('/owner','revisions')).rejects.toThrow('continuation cursor')
    fixture.get.mockResolvedValue({records:[],watermark:'second',has_more:false,next_cursor:null})
    await expect(ledgerPage('/owner','deployments','cursor','first')).rejects.toThrow('watermark changed')
  })
  it('sends only changed author files with exact generation and sensitive logging',async()=>{
    await saveEditor('/owner',{draft:{draft_id:'d',generation:3} as never,entrypoint_path:'agent.yaml',files:[{path:'agent.yaml',editable:true,content:'old'},{path:'woobe.yaml',editable:false,content:null}]},{'agent.yaml':'new'},'operation')
    expect(fixture.put).toHaveBeenCalledWith('/owner/drafts/d/editor',{operation_id:'operation',expected_generation:3,files:[{path:'agent.yaml',content:'new'}]},{sensitive:true})
  })
  it('refuses incomplete or imprecise private fencing proof',()=>{
    expect(()=>leaseProof({lease_id:'lease',workflow_id:'workflow',fencing_token:9007199254740992})).toThrow('incomplete')
    expect(()=>leaseProof({lease_id:'lease',fencing_token:2})).toThrow('incomplete')
  })
})
