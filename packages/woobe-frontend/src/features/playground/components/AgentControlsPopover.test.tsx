import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { AgentControlsPopover } from './AgentControlsPopover'
import type { Agent } from '@/features/agents/types'

const fixture = vi.hoisted(() => ({ state: { data: undefined as unknown, isError: false, isLoading: false } }))
vi.mock('@/features/agents/hooks', () => ({
  useAgentRuntimeEnvironments: () => fixture.state,
  useUpdateAgentRuntimeEnvironment: () => ({ isPending: false }),
}))
const render = () => renderToStaticMarkup(<AgentControlsPopover agent={{id:'a'} as Agent} projectId="p" />)
describe('runtime control observation', () => {
  it('does not turn an unavailable read or stale cached flags into 0/3', () => {
    fixture.state = { data: {draft:{enabled:true},staging:{enabled:true},production:{enabled:true}}, isError: true, isLoading: false }
    expect(render()).toContain('>Unknown<'); expect(render()).not.toContain('0/3')
    fixture.state = { data: undefined, isError: false, isLoading: true }
    expect(render()).toContain('>…<')
  })
  it('keeps explicit disabled flags distinct from missing flags', () => {
    fixture.state = { data: {draft:{enabled:false},staging:{enabled:false},production:{enabled:false}}, isError: false, isLoading: false }
    expect(render()).toContain('>0/3<')
    fixture.state.data = {draft:{enabled:false}}
    expect(render()).toContain('>Unknown<')
  })
})
