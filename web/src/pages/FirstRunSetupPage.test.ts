import { describe, expect, it } from 'vitest'

import {
  firstRunExitPath,
  firstRunPlaygroundPath,
  firstRunProjectSetupPath,
} from './FirstRunSetupPage'

describe('first-run setup paths', () => {
  it('continues Project creation inside the same setup flow', () => {
    expect(firstRunProjectSetupPath('org-1', 'project-1'))
      .toBe('/organizations/org-1/projects/project-1/setup')
  })

  it('opens the created Agent directly in the explicit first-run Playground', () => {
    expect(firstRunPlaygroundPath('org-1', 'project-1', 'agent-1'))
      .toBe('/organizations/org-1/projects/project-1/agents/agent-1/playground?firstRun=1')
  })

  it('uses the correct exit destination before and after Project creation', () => {
    expect(firstRunExitPath('org-1'))
      .toBe('/organizations/org-1/projects')
    expect(firstRunExitPath('org-1', 'project-1'))
      .toBe('/organizations/org-1/projects/project-1/agents')
  })
})
