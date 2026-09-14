import { describe, expect, it } from 'vitest'

import {
  getRagStrategy,
  mergeRagRuntimeConfig,
  normalizeRagStrategy,
  withRagStrategy,
} from './ragStrategyConfig'

describe('RAG strategy runtime configuration', () => {
  it('defaults missing or blank strategy to classic and normalizes explicit names', () => {
    expect(getRagStrategy({})).toBe('classic')
    expect(getRagStrategy({ rag: {} })).toBe('classic')
    expect(normalizeRagStrategy('  Agentic  ')).toBe('agentic')
    expect(normalizeRagStrategy('   ')).toBe('classic')
  })

  it('changes only the RAG strategy while preserving runtime and strategy-specific configuration', () => {
    const runtimeConfig = {
      context_manager: { name: 'default' },
      rag: {
        strategy: 'classic',
        top_k: 8,
        strategy_config: { max_iterations: 3 },
      },
    }

    expect(withRagStrategy(runtimeConfig, ' Agentic ')).toEqual({
      context_manager: { name: 'default' },
      rag: {
        strategy: 'agentic',
        top_k: 8,
        strategy_config: { max_iterations: 3 },
      },
    })
  })

  it('merges retrieval changes without erasing the selected strategy or future strategy config', () => {
    const runtimeConfig = {
      rag: {
        strategy: 'agentic',
        top_k: 5,
        strategy_config: { max_iterations: 4 },
      },
    }

    expect(mergeRagRuntimeConfig(runtimeConfig, { top_k: 10, candidate_k: 20 })).toEqual({
      rag: {
        strategy: 'agentic',
        top_k: 10,
        candidate_k: 20,
        strategy_config: { max_iterations: 4 },
      },
    })
  })
})
