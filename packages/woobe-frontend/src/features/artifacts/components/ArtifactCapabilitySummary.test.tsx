import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ArtifactCapabilitySummary } from './ArtifactCapabilitySummary'

describe('Artifact capability snapshot summary', () => {
  it('shows the pinned policy without exposing Workspace identities or credentials', () => {
    const html = renderToStaticMarkup(<ArtifactCapabilitySummary label="Node policy" runtimeConfig={{
      artifacts: {
        enabled: true,
        workspace_binding: { field: 'artifact_workspace', namespace: 'study-files', scope: 'session' },
        actions: ['read', 'search'],
        limits: { max_read_chars: 4096, max_total_read_chars: 16000, max_context_units: 2000 },
        processing_profile: { ref: 'native', revision: 3 },
        private_workspace_id: 'must-not-display',
      },
    }} />)

    expect(html).toContain('session')
    expect(html).toContain('study-files')
    expect(html).toContain('native r3')
    expect(html).not.toContain('must-not-display')
    expect(html).toContain('server still evaluates current Project and Workspace grants')
  })
})
