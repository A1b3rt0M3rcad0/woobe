import { RUNTIME_STREAM_RETRY_BASE_MS } from './protocol'
import type { RuntimeOutputReconciliation } from './types'

export function runtimeRetryDelayMs(attempt: number): number {
  return RUNTIME_STREAM_RETRY_BASE_MS * (attempt + 1)
}

export function reconcileRuntimeOutput(
  currentOutput: string,
  nextOutput: string,
): RuntimeOutputReconciliation {
  if (currentOutput === nextOutput) {
    return {
      output: nextOutput,
      append: '',
      retract: 0,
      changed: false,
    }
  }

  if (nextOutput.startsWith(currentOutput)) {
    return {
      output: nextOutput,
      append: nextOutput.slice(currentOutput.length),
      retract: 0,
      changed: true,
    }
  }

  return {
    output: nextOutput,
    append: nextOutput,
    retract: currentOutput.length,
    changed: true,
  }
}
