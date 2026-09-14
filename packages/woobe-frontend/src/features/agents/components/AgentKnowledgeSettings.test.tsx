// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const fixture = vi.hoisted(() => ({
  setField: vi.fn(),
  createKnowledgeVersion: vi.fn(),
  state: {
    knowledgeVersionId: null as string | null,
    runtimeConfig: {
      context_manager: { name: 'default' },
      rag: {
        top_k: 7,
        strategy_config: { max_iterations: 3 },
      },
    } as Record<string, unknown>,
  },
}))

vi.mock('@/features/agents/hooks', () => ({
  useKnowledgeVersions: () => ({ data: [] }),
  useCreateKnowledgeVersion: () => ({ mutateAsync: fixture.createKnowledgeVersion }),
}))

vi.mock('@/features/knowledge/hooks', () => ({
  useCollections: () => ({ data: [] }),
}))

vi.mock('@/features/knowledge/ragStrategies', () => ({
  useRagStrategies: () => ({
    data: [
      {
        name: 'classic',
        display_name: 'Classic RAG',
        description: 'Classic semantic retrieval.',
        is_default: true,
      },
      {
        name: 'agentic',
        display_name: 'Agentic RAG',
        description: 'Iterative agent-driven retrieval.',
        is_default: false,
      },
    ],
    isLoading: false,
  }),
}))

vi.mock('@/features/playground/AgentEditorContext', () => ({
  useAgentEditor: () => ({ state: fixture.state, setField: fixture.setField }),
}))

vi.mock('@/features/knowledge/components/SelectKnowledgeVersionModal', () => ({
  SelectKnowledgeVersionModal: () => null,
}))

vi.mock('@/features/playground/components/ManageKnowledgeModal', () => ({
  ManageKnowledgeModal: () => null,
}))

vi.mock('@/features/playground/components/RagRuntimeSettings', () => ({
  RagRuntimeSettings: () => null,
}))

import { AgentKnowledgeSettings } from './AgentKnowledgeSettings'

let root: Root
let container: HTMLDivElement

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  fixture.setField.mockReset()
  fixture.createKnowledgeVersion.mockReset()
  fixture.state.knowledgeVersionId = null
  fixture.state.runtimeConfig = {
    context_manager: { name: 'default' },
    rag: {
      top_k: 7,
      strategy_config: { max_iterations: 3 },
    },
  }
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

describe('Agent Knowledge execution settings', () => {
  it('splits Knowledge into Sources, Retrieval and Execution tabs', async () => {
    await act(async () => {
      root.render(<AgentKnowledgeSettings projectId="project-1" agentId="agent-1" />)
    })

    const tabs = Array.from(container.querySelectorAll<HTMLElement>('[role="tab"]'))
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Sources', 'Retrieval', 'Execution'])
    expect(tabs[0]?.getAttribute('aria-selected')).toBe('true')
    expect(container.textContent).toContain('No knowledge selected')

    await act(async () => tabs[2]?.click())

    expect(tabs[2]?.getAttribute('aria-selected')).toBe('true')
    expect(container.textContent).toContain('RAG execution')
    expect(container.textContent).toContain('Classic RAG')
  })

  it('defaults to classic and writes a selected catalog strategy without erasing runtime config', async () => {
    await act(async () => {
      root.render(<AgentKnowledgeSettings projectId="project-1" agentId="agent-1" />)
    })

    const executionTab = Array.from(container.querySelectorAll<HTMLElement>('[role="tab"]'))
      .find((tab) => tab.textContent === 'Execution')
    await act(async () => executionTab?.click())

    const select = container.querySelector<HTMLSelectElement>('select[aria-label="RAG Strategy"]')
    expect(select).not.toBeNull()
    expect(select?.value).toBe('classic')
    expect(Array.from(select?.options ?? []).map((option) => option.textContent)).toEqual([
      'Classic RAG',
      'Agentic RAG',
    ])

    await act(async () => {
      if (!select) return
      select.value = 'agentic'
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })

    expect(fixture.setField).toHaveBeenCalledWith('runtimeConfig', {
      context_manager: { name: 'default' },
      rag: {
        top_k: 7,
        strategy_config: { max_iterations: 3 },
        strategy: 'agentic',
      },
    })
  })
})
