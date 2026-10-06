// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from './api'
import { WorkspaceCliKeys } from './WorkspaceCliKeys'

vi.mock('./api', () => ({
  getEffectiveAccess: vi.fn(),
  getPermissionCatalog: vi.fn(),
  listControlKeys: vi.fn(),
  listAuthorityCategories: vi.fn(),
  createControlKey: vi.fn(),
  rotateControlKey: vi.fn(),
  revokeControlKey: vi.fn(),
}))

const workspaceId = 'workspace-a'
const project = {
  id: 'project-a',
  workspace_id: workspaceId,
  name: 'Project A',
  slug: 'project-a',
}
const metadata: api.ControlKey = {
  id: 'key-a',
  name: 'Workstation',
  description: null,
  key_prefix: 'woobe_control_prefix',
  status: 'active',
  permissions: ['workspace:read'],
  project_grants: [],
  on_project_create_permissions: [],
  expires_at: null,
  created_at: '2026-10-06T00:00:00Z',
  etag: '"control-key:key-a:1"',
}
const editorRole: api.AuthorityCategory = {
  id: 'category-editor',
  name: 'agent-editor',
  scope: 'project',
  description: null,
  revision: 1,
  permissions: ['agent:read', 'agent:write'],
  conditions: {},
  system: true,
  status: 'active',
}
const secret = 'woobe_control_test_secret_only'
let container: HTMLDivElement
let root: Root
let client: QueryClient

async function flush() {
  for (let attempt = 0; attempt < 100; attempt++) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
    if (
      client.isFetching() === 0 &&
      !container.textContent?.includes('Loading ')
    )
      return
  }
  throw new Error('CLI key queries did not settle')
}
function button(text: string) {
  const match = [...container.querySelectorAll('button')].find(
    (node) => node.textContent === text,
  )
  expect(match, text).toBeTruthy()
  return match!
}
async function click(node: HTMLElement) {
  await act(async () => node.click())
  await flush()
}
async function type(id: string, value: string) {
  const node = container.querySelector<HTMLInputElement>(`#${id}`)!
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      'value',
    )!.set!.call(node, value)
    node.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
async function render() {
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>
        <WorkspaceCliKeys workspaceId={workspaceId} projects={[project]} />
      </QueryClientProvider>,
    ),
  )
  await flush()
}

beforeEach(() => {
  vi.resetAllMocks()
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  vi.mocked(api.getEffectiveAccess).mockImplementation(
    async (_, projectId): Promise<api.EffectiveAccess> => ({
      permissions: projectId
        ? ['agent:read', 'agent:write']
        : [
            'workspace:read',
            'keys:read',
            'keys:create',
            'keys:rotate',
            'keys:revoke',
          ],
      conditions: {},
    }),
  )
  vi.mocked(api.getPermissionCatalog).mockResolvedValue({
    permissions: {
      workspace: ['workspace:read'],
      project: ['agent:read', 'agent:write', 'secret:write'],
    },
  })
  vi.mocked(api.listAuthorityCategories).mockResolvedValue([editorRole])
  vi.mocked(api.listControlKeys).mockResolvedValue([])
  vi.mocked(api.createControlKey).mockResolvedValue({
    ...metadata,
    key: secret,
  })
  vi.mocked(api.rotateControlKey).mockResolvedValue({
    ...metadata,
    id: 'replacement',
    key: secret,
  })
  vi.mocked(api.revokeControlKey).mockResolvedValue({
    ...metadata,
    status: 'revoked',
  })
})
afterEach(async () => {
  await act(async () => root.unmount())
  client.clear()
  container.remove()
})

describe('Workspace CLI key management', () => {
  it('creates explicit grants and keeps the one-time secret out of query/mutation caches', async () => {
    await render()
    await click(button('Create CLI key'))
    await type('cli-key-name', 'Workstation')
    await click(button('No expiration'))
    await click(button('Workspace'))
    await click(
      container.querySelector<HTMLElement>('[aria-label="Custom access"]')!,
    )
    await click(
      container.querySelector<HTMLInputElement>(
        'input[aria-label="workspace:read"]',
      )!,
    )
    await click(button('Projects (0)'))
    expect(
      container.querySelector('input[aria-label="secret:write"]'),
    ).toBeNull()
    await click(
      container.querySelector<HTMLElement>('[aria-label="Agent Editor"]')!,
    )
    await click(button('Create key'))
    expect(api.createControlKey).toHaveBeenCalledWith(
      workspaceId,
      {
        name: 'Workstation',
        description: null,
        expires_at: null,
        permissions: ['workspace:read'],
        project_grants: [
          {
            project_id: project.id,
            permissions: ['agent:read', 'agent:write'],
            conditions: {},
            category_id: editorRole.id,
            category_revision: editorRole.revision,
          },
        ],
        on_project_create_permissions: [],
      },
      expect.any(String),
    )
    expect(container.textContent).toContain(secret)
    expect(
      JSON.stringify(
        client
          .getQueryCache()
          .getAll()
          .map((entry) => entry.state.data),
      ),
    ).not.toContain(secret)
    expect(client.getMutationCache().getAll()).toHaveLength(0)
    await click(button('I saved the key'))
    expect(container.textContent).not.toContain(secret)
  })

  it('disables roles whose permissions exceed the issuer access', async () => {
    vi.mocked(api.getEffectiveAccess).mockImplementation(
      async (_, projectId): Promise<api.EffectiveAccess> => ({
        permissions: projectId ? ['agent:read'] : ['keys:read', 'keys:create'],
        conditions: {},
      }),
    )
    await render()
    await click(button('Create CLI key'))
    await type('cli-key-name', 'Restricted integration')
    const role = container.querySelector<HTMLElement>(
      '[aria-label="Agent Editor"]',
    )!
    expect(role.getAttribute('aria-disabled')).toBe('true')
    await click(role)
    expect((button('Create key') as HTMLButtonElement).disabled).toBe(true)
    expect(api.createControlKey).not.toHaveBeenCalled()
  })

  it('pins the selected category revision and preserves inherited restrictions', async () => {
    vi.mocked(api.listAuthorityCategories).mockResolvedValue([
      {
        ...editorRole,
        revision: 3,
        conditions: { environments: ['staging', 'production'] },
      },
    ])
    vi.mocked(api.getEffectiveAccess).mockImplementation(
      async (_, projectId): Promise<api.EffectiveAccess> => ({
        permissions: projectId
          ? ['agent:read', 'agent:write']
          : ['keys:read', 'keys:create'],
        conditions: projectId
          ? { environments: ['staging'], target_ids: ['agent-a'] }
          : {},
      }),
    )
    await render()
    await click(button('Create CLI key'))
    await type('cli-key-name', 'Staging integration')
    await click(
      container.querySelector<HTMLElement>('[aria-label="Agent Editor"]')!,
    )
    await click(button('Create key'))
    expect(api.createControlKey).toHaveBeenCalledWith(
      workspaceId,
      expect.objectContaining({
        project_grants: [
          {
            project_id: project.id,
            permissions: ['agent:read', 'agent:write'],
            category_id: editorRole.id,
            category_revision: 3,
            conditions: { environments: ['staging'], target_ids: ['agent-a'] },
          },
        ],
      }),
      expect.any(String),
    )
  })

  it('does not load credentials or offer creation without effective read permission', async () => {
    vi.mocked(api.getEffectiveAccess).mockResolvedValue({
      permissions: ['access:self'],
      conditions: {},
    })
    await render()
    expect(container.textContent).toContain('CLI key management is restricted')
    expect(api.listControlKeys).not.toHaveBeenCalled()
    expect(api.createControlKey).not.toHaveBeenCalled()
  })

  it('requires confirmation and the observed resource revision for rotation and revocation', async () => {
    vi.mocked(api.listControlKeys).mockResolvedValue([metadata])
    await render()
    await click(button('Rotate Workstation'))
    expect(api.rotateControlKey).not.toHaveBeenCalled()
    await click(button('Confirm rotation'))
    expect(api.rotateControlKey).toHaveBeenCalledWith(
      workspaceId,
      metadata,
      expect.any(String),
    )
    expect(container.textContent).toContain(secret)
    await click(button('I saved the key'))
    await click(button('Revoke Workstation'))
    expect(api.revokeControlKey).not.toHaveBeenCalled()
    await click(button('Confirm revocation'))
    expect(api.revokeControlKey).toHaveBeenCalledWith(workspaceId, metadata)
  })
})
