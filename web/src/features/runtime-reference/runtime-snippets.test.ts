import { describe, expect, it } from 'vitest'

import {
  buildRuntimeSnippet,
  RUNTIME_CODE_LANGUAGES,
  type RuntimeCodeLanguage,
} from './runtime-snippets'

const languages = RUNTIME_CODE_LANGUAGES.map((item) => item.value)

describe('runtime API snippets', () => {
  it('exposes the supported copy-paste languages', () => {
    expect(languages).toEqual(['curl', 'python', 'javascript', 'java', 'ruby', 'go'])
  })

  it.each(languages)('generates an authenticated HTTP example for %s', (language) => {
    const snippet = buildRuntimeSnippet({
      language: language as RuntimeCodeLanguage,
      runtimeInterface: 'http',
      baseUrl: 'https://api.example.com',
      body: { message: 'Hello!' },
      includeIdempotencyKey: true,
    })

    expect(snippet).toContain('https://api.example.com/v1/run')
    expect(snippet).toContain('WOOBE_API_KEY')
    expect(snippet).toContain('Idempotency-Key')
    expect(snippet).not.toContain('/v1/jobs')
  })

  it.each(languages)('generates a streaming example for %s', (language) => {
    const snippet = buildRuntimeSnippet({
      language: language as RuntimeCodeLanguage,
      runtimeInterface: 'stream',
      baseUrl: 'https://api.example.com',
      body: { message: 'Hello!' },
    })

    expect(snippet).toContain('https://api.example.com/v1/run/stream')
    expect(snippet).toContain('WOOBE_API_KEY')
  })
})
