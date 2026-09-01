import { renderToStaticMarkup } from 'react-dom/server'
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
})
