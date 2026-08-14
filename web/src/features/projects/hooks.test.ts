import { describe, expect, it } from 'vitest'

import { upsertProject } from './hooks'
import type { Project } from './types'

const createdProject: Project = {
  id: 'project-1',
  workspace_id: 'workspace-1',
  name: 'First Project',
  slug: 'first-project',
}

describe('upsertProject', () => {
  it('adds a newly created Project to an empty workspace cache', () => {
    expect(upsertProject(undefined, createdProject)).toEqual([createdProject])
  })

  it('replaces the cached Project without creating duplicates', () => {
    const updatedProject = { ...createdProject, name: 'Updated Project' }

    expect(upsertProject([createdProject], updatedProject)).toEqual([updatedProject])
  })

  it('preserves the other Projects in the Workspace', () => {
    const existingProject: Project = {
      id: 'project-2',
      workspace_id: 'workspace-1',
      name: 'Existing Project',
      slug: 'existing-project',
    }

    expect(upsertProject([existingProject], createdProject)).toEqual([
      existingProject,
      createdProject,
    ])
  })
})
