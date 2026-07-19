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

  it.each(languages)('generates an authenticated HTTP example for %s', (language) => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: language as RuntimeCodeLanguage,
      runtimeInterface: 'http',
    })

    expect(snippet).toContain('https://api.example.com/v1/run')
    expect(snippet).toContain('WOOBE_API_KEY')
    expect(snippet).toContain('Idempotency-Key')
    expect(snippet).not.toContain('/v1/jobs')
  })

  it('prints only the public HTTP result in Python', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'python',
      runtimeInterface: 'http',
    })

    expect(snippet).toContain('print(run.get("parsed_output") or run["answer"])')
    expect(snippet).not.toContain('print(response.json())')
  })

  it('filters Python streaming output to public final phases', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'python',
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('final_response_generation')
    expect(snippet).toContain('network_result')
    expect(snippet).not.toContain('print(line)')
  })

  it.each(languages)('generates a streaming example for %s', (language) => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: language as RuntimeCodeLanguage,
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('https://api.example.com/v1/run/stream')
    expect(snippet).toContain('WOOBE_API_KEY')
  })
})
