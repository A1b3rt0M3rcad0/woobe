import { describe, expect, it } from 'vitest'

import networkWorkspaceSource from '@/features/network/components/NetworkChatWorkspace.tsx?raw'
import playgroundSource from '@/pages/AgentPlaygroundPage.tsx?raw'

describe('Run reattach orchestration policy', () => {
  it('waits for persisted Session hydration before Standalone reattach discovery', () => {
    expect(playgroundSource).toContain(
      'historyMessages && selectedSessionId && !isSending && !isFetching',
    )
    expect(playgroundSource).toContain(
      'if (!projectId || !agentId || isSending || isFetching) return',
    )
    expect(playgroundSource).toContain(
      '[agentId, environment, isFetching, isSending, projectId, reattach',
    )
  })

  it('releases Standalone observer ownership after transport exit so the same Run can reattach again', () => {
    expect(playgroundSource).toMatch(
      /finally\s*{\s*if \(reattachingRunRef\.current === runId\) {\s*reattachingRunRef\.current = null\s*}\s*if \(mountedRef\.current\) setIsSending\(false\)/,
    )
  })

  it('restores mounted markers during effect setup for React StrictMode remount probes', () => {
    expect(playgroundSource).toMatch(
      /useEffect\(\(\) => {\s*mountedRef\.current = true\s*return \(\) => { mountedRef\.current = false }\s*}, \[\]\)/,
    )
    expect(networkWorkspaceSource).toMatch(
      /useLayoutEffect\(\(\) => {\s*mountedRef\.current = true\s*return \(\) => {\s*mountedRef\.current = false/,
    )
  })

  it('stops showing execution activity below Network output once the public answer starts streaming', () => {
    expect(networkWorkspaceSource).toMatch(
      /activity:\s*liveAnswer\s*\?\s*null\s*:\s*{/,
    )
  })
})
