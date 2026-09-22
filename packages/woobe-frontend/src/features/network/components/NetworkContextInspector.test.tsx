import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import { createEmptyNetworkDefinition } from '../editor/networkDefinitionMapper'
import { NetworkContextInspector } from './NetworkContextInspector'

describe('Network context inspector bootstrap', () => {
  it('returns the full workspace loading surface before an editable definition is hydrated', () => {
    const markup = renderToStaticMarkup(
      <NetworkContextInspector
        context="network"
        centerMode="canvas"
        inspectionScope={{ type: 'current' }}
        definition={createEmptyNetworkDefinition()}
        agents={[]}
        bindings={{}}
        issues={[]}
        selection={{ type: 'network' }}
        readOnly={false}
        name="Project Network"
        description=""
        agentWorkspace={null}
        onContext={vi.fn()}
        onLocateOnCanvas={vi.fn()}
        onSelect={vi.fn()}
        onMetadata={vi.fn()}
        onChange={vi.fn()}
      />,
    )

    expect(markup).toContain('Preparing Network')
    expect(markup).not.toContain('Node settings')
  })

  it.each(['chat', 'canvas'] as const)('uses the same responsive inspector width in %s mode', (centerMode) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    const markup = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <NetworkContextInspector
          context="network"
          centerMode={centerMode}
          inspectionScope={{ type: 'current' }}
          definition={createEmptyNetworkDefinition()}
          agents={[]}
          bindings={{}}
          issues={[]}
          selection={{ type: 'network' }}
          readOnly
          name="Project Network"
          description=""
          agentWorkspace={null}
          onContext={vi.fn()}
          onLocateOnCanvas={vi.fn()}
          onSelect={vi.fn()}
          onMetadata={vi.fn()}
          onChange={vi.fn()}
        />
      </QueryClientProvider>,
    )

    expect(markup).toContain('xl:w-inspector-workspace')
    expect(markup).toContain('w-[min(94vw,32.5rem)]')
    expect(markup).not.toContain('w-[400px]')
    expect(markup).not.toContain('w-[520px]')
  })
})
