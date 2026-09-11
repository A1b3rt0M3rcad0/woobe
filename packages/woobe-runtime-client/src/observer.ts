import { RUNTIME_STREAM_RETRY_BASE_MS } from './protocol'
import type { RuntimeOutputReconciliation } from './types'

function runtimeAbortError(): DOMException {
  return new DOMException('Runtime stream retry aborted', 'AbortError')
}

function browserIsOffline(): boolean {
  return (
    typeof window !== 'undefined'
    && typeof navigator !== 'undefined'
    && navigator.onLine === false
  )
}

async function waitForBrowserOnline(signal?: AbortSignal): Promise<boolean> {
  if (!browserIsOffline()) return false
  if (signal?.aborted) throw runtimeAbortError()

  await new Promise<void>((resolve, reject) => {
    let settled = false

    const cleanup = () => {
      window.removeEventListener('online', onOnline)
      signal?.removeEventListener('abort', onAbort)
    }
    const onOnline = () => {
      if (settled) return
      settled = true
      cleanup()
      resolve()
    }
    const onAbort = () => {
      if (settled) return
      settled = true
      cleanup()
      reject(runtimeAbortError())
    }

    window.addEventListener('online', onOnline, { once: true })
    signal?.addEventListener('abort', onAbort, { once: true })
    if (signal?.aborted) onAbort()
    else if (!browserIsOffline()) onOnline()
  })
  return true
}

export function runtimeRetryDelayMs(attempt: number): number {
  return RUNTIME_STREAM_RETRY_BASE_MS * (attempt + 1)
}

export async function waitForRuntimeRetry(
  attempt: number,
  signal?: AbortSignal,
): Promise<void> {
  if (await waitForBrowserOnline(signal)) return
  if (signal?.aborted) throw runtimeAbortError()

  await new Promise<void>((resolve, reject) => {
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, runtimeRetryDelayMs(attempt))

    const onAbort = () => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(runtimeAbortError())
    }

    signal?.addEventListener('abort', onAbort, { once: true })
    if (signal?.aborted) onAbort()
  })
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
