// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamCallbacks } from './stream-client'

const fixture = vi.hoisted(() => ({
  client: { invalidateQueries: vi.fn() },
  reattach: vi.fn(),
}))
vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => fixture.client }))
vi.mock('./stream-client', () => ({ askStreamV1: vi.fn(), reattachAgentRunV1: fixture.reattach }))
import { useAskStream } from './hooks'

let hook: ReturnType<typeof useAskStream>
let root: Root
function Harness() { hook = useAskStream(); return null }
const callbacks = (): StreamCallbacks => ({
  onMeta: vi.fn(), onToken: vi.fn(), onSources: vi.fn(), onDone: vi.fn(), onError: vi.fn(),
})
beforeEach(async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  vi.clearAllMocks()
  root = createRoot(document.createElement('div'))
  await act(async () => root.render(<Harness />))
})
afterEach(async () => { await act(async () => root.unmount()) })

it('does not refetch caches or swallow rejection when its observer disconnects', async () => {
  fixture.reattach.mockImplementation((_runId: string, cb: StreamCallbacks, signal: AbortSignal) => {
    cb.onMeta({ run_id: 'run-1', session_id: 'session-1' })
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Disconnected', 'AbortError'))))
  })
  const result = hook.reattach('run-1', callbacks()).catch(error => error)
  fixture.client.invalidateQueries.mockClear()
  hook.disconnect()
  expect((await result).name).toBe('AbortError')
  expect(fixture.client.invalidateQueries).not.toHaveBeenCalled()
})

it('does not let the previous controller refresh a replacement Session', async () => {
  const pending: Array<{ resolve: () => void }> = []
  fixture.reattach.mockImplementation((runId: string, cb: StreamCallbacks) => {
    cb.onMeta({ run_id: runId, session_id: `session-${runId}` })
    return new Promise<void>(resolve => pending.push({ resolve }))
  })
  const first = hook.reattach('one', callbacks())
  const second = hook.reattach('two', callbacks())
  fixture.client.invalidateQueries.mockClear()
  pending[0].resolve()
  await first
  expect(fixture.client.invalidateQueries).not.toHaveBeenCalled()
  pending[1].resolve()
  await second
  expect(fixture.client.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['session-messages', 'session-two'] })
})
