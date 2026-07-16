import { describe, expect, it } from 'vitest'

import type { ChatMessage } from '@/features/playground/types'
import {
  didCompleteFirstRun,
  isFirstRunSearch,
  removeFirstRunFromLocation,
} from './first-run'

const successfulMessages: ChatMessage[] = [
  { role: 'user', content: 'Hello' },
  { role: 'assistant', content: 'Hi there' },
]

describe('playground first run', () => {
  it('recognizes the explicit query marker', () => {
    expect(isFirstRunSearch('?firstRun=1')).toBe(true)
    expect(isFirstRunSearch('?firstRun=0')).toBe(false)
    expect(isFirstRunSearch('')).toBe(false)
  })

  it('requires a completed send transition and a valid assistant response', () => {
    expect(didCompleteFirstRun(true, false, successfulMessages)).toBe(true)
    expect(didCompleteFirstRun(false, false, successfulMessages)).toBe(false)
    expect(didCompleteFirstRun(true, true, successfulMessages)).toBe(false)
    expect(didCompleteFirstRun(true, false, [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Invalid', output_parse_error: 'schema mismatch' },
    ])).toBe(false)
  })

  it('removes only the first-run marker from the location', () => {
    expect(removeFirstRunFromLocation('/playground', '?firstRun=1&panel=debug', '#trace'))
      .toBe('/playground?panel=debug#trace')
    expect(removeFirstRunFromLocation('/playground', '?firstRun=1'))
      .toBe('/playground')
  })
})
