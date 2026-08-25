import { describe, expect, it } from 'vitest'

import {
  firstRunExitPath,
  firstRunPlaygroundPath,
  firstRunProjectSetupPath,
} from './FirstRunSetupPage'

describe('first-run setup paths', () => {
  it('continues Project creation inside the same setup workspace', () => {
    expect(firstRunProjectSetupPath('workspace-1', 'project-1'))
      .toBe('/workspaces/workspace-1/projects/project-1/setup')
  })

  it('keeps Agent details, model and review inside one stable setup route', () => {
    const setupPath = firstRunProjectSetupPath('workspace-1', 'project-1')
    expect(setupPath).not.toContain('/details')
    expect(setupPath).not.toContain('/model')
    expect(setupPath).not.toContain('/review')
  })

  it('opens the created Agent directly in the explicit first-run Playground', () => {
    expect(firstRunPlaygroundPath('workspace-1', 'project-1', 'agent-1'))
      .toBe('/workspaces/workspace-1/projects/project-1/agents/agent-1/playground?firstRun=1')
  })

  it('uses the correct exit destination before and after Project creation', () => {
    expect(firstRunExitPath('workspace-1'))
      .toBe('/workspaces/workspace-1/projects')
    expect(firstRunExitPath('workspace-1', 'project-1'))
      .toBe('/workspaces/workspace-1/projects/project-1/agents')
  })
})
