// @vitest-environment jsdom
import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Dialog } from '@woobe/ui'

let root: Root
let container: HTMLDivElement

function FocusProbe({ onClose }: { onClose: (value: string) => void }) {
  const [value, setValue] = useState('')

  return (
    <Dialog open onClose={() => onClose(value)} title="Focus probe">
      <input
        aria-label="Probe input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
    </Dialog>
  )
}

async function flushFrame() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => setTimeout(() => callback(performance.now()), 0) as unknown as number)
  vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('Dialog focus lifecycle', () => {
  it('does not rerun autofocus when an unstable onClose changes during typing', async () => {
    const onClose = vi.fn()

    await act(async () => {
      root.render(<FocusProbe onClose={onClose} />)
    })
    await flushFrame()

    const input = document.querySelector<HTMLInputElement>('input[aria-label="Probe input"]')
    expect(input).toBeTruthy()

    await act(async () => input!.focus())
    expect(document.activeElement).toBe(input)

    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'typed value')
      input!.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await flushFrame()

    expect(document.activeElement).toBe(input)

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })

    expect(onClose).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledWith('typed value')
  })
})
