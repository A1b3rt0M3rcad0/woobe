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
  targetType: 'network',
  targetName: 'Support Network',
  environment: 'staging',
  version: 'staging-r1',
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
    expect(snippet).toContain('paste_your_runtime_key_here')
    expect(snippet).toContain('Idempotency-Key')
    expect(snippet).not.toContain('/v1/jobs')
  })

  it('prints a limited Network Run summary in Python', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'python',
      runtimeInterface: 'http',
    })

    expect(snippet).toContain('✓ {run_label} completed')
    expect(snippet).toContain('print_field("Run ID", run.get("execution_id"))')
    expect(snippet).toContain('print_field("Session"')
    expect(snippet).toContain('print_field("Trace"')
    expect(snippet).toContain('Structured result')
    expect(snippet).not.toContain('print(response.json())')
  })

  it('prints Agent provider, model, usage, and public result', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      targetType: 'agent',
      targetName: 'Support Agent',
      version: 'staging-r2',
      language: 'javascript',
      runtimeInterface: 'http',
      includeIdempotencyKey: false,
    })

    expect(snippet).toContain("printField('Provider', run.provider)")
    expect(snippet).toContain("printField('Model', run.model)")
    expect(snippet).toContain("printField('Tokens', run.usage?.total_tokens)")
    expect(snippet).toContain('printResult(run)')
  })

  it('filters Python streaming output to public final phases and prints completion metadata', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'python',
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('final_response_generation')
    expect(snippet).toContain('network_result')
    expect(snippet).toContain('print_stream_completion(terminal)')
    expect(snippet).not.toContain('print(line)')
  })

  it('documents raw SSE only for cURL streaming', () => {
    const snippet = buildRuntimeSnippet({
      ...baseInput,
      language: 'curl',
      runtimeInterface: 'stream',
    })

    expect(snippet).toContain('raw SSE protocol')
    expect(snippet).toContain('curl -sS -N')
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
