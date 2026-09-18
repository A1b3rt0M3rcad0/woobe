import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import type { Agent } from '@/features/agents/types'
import { AgentInspector } from './AgentInspector'

describe('Agent inspector layout', () => {
  const agent = {
    id: 'agent-1',
    project_id: 'project-1',
    name: 'Support Agent',
  } as Agent

  it('uses the responsive workspace inspector width without an expand control', () => {
    const markup = renderToStaticMarkup(
      <AgentInspector
        agent={agent}
        projectId="project-1"
        agentId="agent-1"
        activeTab="editor"
        environment="staging"
        environmentRelease={null}
        onTabChange={vi.fn()}
        onCollapse={vi.fn()}
      />,
    )

    expect(markup).toContain('lg:w-inspector-workspace')
    expect(markup).toContain('w-[min(94vw,32.5rem)]')
    expect(markup).not.toContain('Expand Inspector')
    expect(markup).not.toContain('Restore Inspector width')
    expect(markup).toContain('Collapse Inspector')
  })
})
