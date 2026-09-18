// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AgentRelease } from '@/features/agents/types'
import type { ChatSurface } from '@/features/chat-surfaces/types'
import { ChatSurfaceLiveTestDialog } from './ChatSurfaceLiveTestDialog'

const fixture = vi.hoisted(() => ({
  createSession: vi.fn(),
  releaseCalls: [] as Array<[string | undefined, string | undefined]>,
  releases: new Map<string, AgentRelease>(),
  loadingReleaseIds: new Set<string>(),
  errorReleaseIds: new Set<string>(),
  networkVersions: [] as Array<Record<string, unknown>>,
}))

vi.mock('@/features/chat-surfaces/api', async original => ({
  ...await original<typeof import('@/features/chat-surfaces/api')>(),
  createChatSurfaceTestSession: fixture.createSession,
}))

vi.mock('@/features/agents/hooks', async original => ({
  ...await original<typeof import('@/features/agents/hooks')>(),
  useRelease: (agentId?: string, releaseId?: string) => {
    fixture.releaseCalls.push([agentId, releaseId])
    return {
      data: releaseId ? fixture.releases.get(releaseId) : undefined,
      isLoading: Boolean(releaseId && fixture.loadingReleaseIds.has(releaseId)),
      isPending: Boolean(releaseId && fixture.loadingReleaseIds.has(releaseId)),
      isError: Boolean(releaseId && fixture.errorReleaseIds.has(releaseId)),
      error: releaseId && fixture.errorReleaseIds.has(releaseId)
        ? new Error('Release unavailable')
        : null,
    }
  },
}))

vi.mock('@/features/network/hooks', async original => ({
  ...await original<typeof import('@/features/network/hooks')>(),
  useNetworkVersions: () => ({
    data: fixture.networkVersions,
    isLoading: false,
    isPending: false,
    isError: false,
    error: null,
  }),
}))

const surface = {
  id: 'surface-1',
  public_id: 'surface-public',
  project_id: 'project-1',
  name: 'ChatBOT',
  target_type: 'agent',
  target_id: 'agent-1',
  target_release_id: 'release-old',
  environment: 'production',
  status: 'active',
} as ChatSurface

const contract = {
  name: {
    schema: { type: 'string' },
    required: true,
    scope: 'session',
    model: { expose: true },
  },
  age: {
    schema: { type: 'integer' },
    required: true,
    scope: 'session',
    model: { expose: false },
  },
}

function release(id: string, externalContextContract: Record<string, unknown>): AgentRelease {
  return {
    id,
    project_id: 'project-1',
    agent_id: 'agent-1',
    version: '1.0.0',
    status: 'production',
    external_context_contract: externalContextContract,
  } as AgentRelease
}

let root: Root
let container: HTMLDivElement
let framePostMessage: ReturnType<typeof vi.fn>

async function flush() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

async function renderDialog() {
  await act(async () => {
    root.render(
      <ChatSurfaceLiveTestDialog
        open
        surface={surface}
        targetName="Meu Agente de Suporte"
        onClose={vi.fn()}
      />,
    )
  })
  await flush()
}

function input(label: string): HTMLInputElement {
  const element = document.querySelector(`input[aria-label="${label}"]`)
  expect(element, label).toBeTruthy()
  return element as HTMLInputElement
}

async function fill(element: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function click(label: string) {
  const button = [...document.querySelectorAll('button')].find(item => item.textContent?.trim() === label)
  expect(button, label).toBeTruthy()
  await act(async () => button!.click())
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  fixture.releaseCalls = []
  fixture.releases = new Map()
  fixture.loadingReleaseIds = new Set()
  fixture.errorReleaseIds = new Set()
  fixture.networkVersions = []
  fixture.createSession.mockReset()
  fixture.createSession.mockResolvedValue({
    session_id: 'session-1',
    target_release_id: 'release-current',
    session_token: 'token',
    expires_in: 3600,
    source: 'control_plane_test',
  })
  framePostMessage = vi.fn()
  Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    configurable: true,
    get: () => ({ postMessage: framePostMessage }),
  })
  vi.stubGlobal('crypto', { randomUUID: () => 'instance-1' })
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('ChatSurface live test External Context', () => {
  it('uses the Release pinned by the created Session to render required fields', async () => {
    fixture.releases.set('release-old', release('release-old', {}))
    fixture.releases.set('release-current', release('release-current', contract))

    await renderDialog()

    expect(fixture.releaseCalls).toContainEqual(['agent-1', 'release-current'])
    expect(document.body.textContent).toContain('name')
    expect(document.body.textContent).toContain('age')
    expect(input('name').placeholder).toBe('Required value')
    expect(input('age').placeholder).toBe('Required value')
    expect(document.body.textContent).not.toContain('No External Context fields are declared for this target.')
  })

  it('does not report an empty contract while the pinned Release is loading', async () => {
    fixture.releases.set('release-old', release('release-old', {}))
    fixture.loadingReleaseIds.add('release-current')

    await renderDialog()

    expect(document.body.textContent).toContain('Loading External Context contract')
    expect(document.body.textContent).not.toContain('No External Context fields are declared for this target.')
  })

  it('shows a contract loading failure instead of pretending the contract is empty', async () => {
    fixture.releases.set('release-old', release('release-old', {}))
    fixture.errorReleaseIds.add('release-current')

    await renderDialog()

    expect(document.body.textContent).toContain('Unable to load External Context contract')
    expect(document.body.textContent).not.toContain('No External Context fields are declared for this target.')
  })

  it('shows the empty state only after the pinned Release loaded with an empty contract', async () => {
    fixture.releases.set('release-current', release('release-current', {}))

    await renderDialog()

    expect(document.body.textContent).toContain('No External Context fields are declared for this target.')
  })

  it('sends the filled contract values to the iframe on Apply context', async () => {
    fixture.releases.set('release-current', release('release-current', contract))

    await renderDialog()
    await fill(input('name'), 'Alberto')
    await fill(input('age'), '18')
    await click('Apply context')

    expect(framePostMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      instanceId: 'instance-1',
      surfaceId: 'surface-public',
      type: 'context.update',
      payload: {
        externalContext: {
          name: 'Alberto',
          age: 18,
        },
      },
    }, 'http://localhost:8081')
  })
})
