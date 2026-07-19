import { describe, expect, it } from 'vitest'

import {
  buildRuntimeSnippet,
  RUNTIME_CODE_LANGUAGES,
  type RuntimeCodeLanguage,
} from './runtime-snippets'

const languages = RUNTIME_CODE_LANGUAGES.map((item) => item.value)

const baseInput = {
  baseUrl: 'https://api.example.com',
  body: { message: 'Hello!' },
  includeIdempotencyKey: true,
} as const

describe('runtime API snippets', () => {
  it('keeps the MVP language set focused', () => {
    expect(languages).toEqual(['python', 'javascript', 'curl'])
  })

  it.each(languages)('generates a concise authenticated HTTP example for %s', (language) => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: language as RuntimeCodeLanguage,
      runtimeInterface: 'http',
    })

    expect(snippet).toContain('https://api.example.com/v1/run')
    expect(snippet).toContain('paste_your_runtime_key_here')
    expect(snippet).toContain('Idempotency-Key')
    expect(snippet).not.toContain('/v1/jobs')
    expect(snippet).not.toContain('Structured result')
    expect(snippet).not.toContain('print_run')
  })

  it('prints the complete HTTP response in Python', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'python',
      runtimeInterface: 'http',
    })

    expect(snippet).toContain('print(response.json())')
    expect(snippet).not.toContain('print_field')
  })

  it('prints raw SSE events in Python', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'python',
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('for line in response.iter_lines')
    expect(snippet).toContain('print(line)')
    expect(snippet).toContain('Each SSE frame')
    expect(snippet).not.toContain('final_response_generation')
  })

  it('prints raw SSE frames in JavaScript', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'javascript',
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('process.stdout.write')
    expect(snippet).toContain('raw SSE frames')
    expect(snippet).not.toContain('network_result')
  })

  it.each(languages)('generates a streaming example for %s', (language) => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: language as RuntimeCodeLanguage,
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('https://api.example.com/v1/run/stream')
    expect(snippet).toContain('paste_your_runtime_key_here')
  })
})
